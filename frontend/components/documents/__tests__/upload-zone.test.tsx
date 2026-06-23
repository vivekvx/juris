import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UploadZone } from "../upload-zone";
import { uploadDocument } from "@/lib/api";
import type { DocumentResponse } from "@/types/document";

vi.mock("@/lib/api", () => ({
  backendPost: vi.fn(),
  uploadDocument: vi.fn(),
}));

vi.mock("@/lib/firebase", () => ({
  getAuth: vi.fn(() => ({
    currentUser: {
      getIdToken: vi.fn().mockResolvedValue("mock-id-token"),
    },
  })),
}));

const mockUpload = vi.mocked(uploadDocument);

const SUCCESS_DOC: DocumentResponse = {
  id: "doc-001",
  filename: "contract.pdf",
  original_filename: "contract.pdf",
  mime_type: "application/pdf",
  size_bytes: 512,
  status: "READY",
  error_message: null,
  created_at: "2024-06-01T12:00:00Z",
  updated_at: "2024-06-01T12:00:00Z",
};

function pickFile(name: string, type: string, sizeOverride?: number): void {
  const file = new File(["content"], name, { type });
  if (sizeOverride !== undefined) {
    Object.defineProperty(file, "size", { value: sizeOverride });
  }
  const input = screen.getByLabelText("Upload document");
  fireEvent.change(input, { target: { files: [file] } });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("UploadZone", () => {
  it("renders upload button", () => {
    render(<UploadZone />);
    expect(
      screen.getByRole("button", { name: /click to choose a file/i }),
    ).toBeInTheDocument();
  });

  it("shows accepted types and size limit", () => {
    render(<UploadZone />);
    expect(screen.getByText(/pdf.*docx.*txt/i)).toBeInTheDocument();
    expect(screen.getByText(/20 mb/i)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Successful uploads
  // -----------------------------------------------------------------------

  it("PDF upload calls uploadDocument with file and token", async () => {
    mockUpload.mockResolvedValue(SUCCESS_DOC);
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() => expect(mockUpload).toHaveBeenCalledOnce());
    const [file, token] = mockUpload.mock.calls[0];
    expect(file.name).toBe("contract.pdf");
    expect(token).toBe("mock-id-token");
  });

  it("DOCX upload calls uploadDocument", async () => {
    const docxType =
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    mockUpload.mockResolvedValue({ ...SUCCESS_DOC, mime_type: docxType });
    render(<UploadZone />);
    pickFile("brief.docx", docxType);
    await waitFor(() => expect(mockUpload).toHaveBeenCalledOnce());
    expect(mockUpload.mock.calls[0][0].name).toBe("brief.docx");
  });

  it("TXT upload calls uploadDocument", async () => {
    mockUpload.mockResolvedValue({ ...SUCCESS_DOC, mime_type: "text/plain" });
    render(<UploadZone />);
    pickFile("notes.txt", "text/plain");
    await waitFor(() => expect(mockUpload).toHaveBeenCalledOnce());
    expect(mockUpload.mock.calls[0][0].name).toBe("notes.txt");
  });

  // -----------------------------------------------------------------------
  // Success state
  // -----------------------------------------------------------------------

  it("shows success state with filename", async () => {
    mockUpload.mockResolvedValue(SUCCESS_DOC);
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByText(/upload complete/i)).toBeInTheDocument();
  });

  it("shows upload-another button after success", async () => {
    mockUpload.mockResolvedValue(SUCCESS_DOC);
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /upload another/i }),
      ).toBeInTheDocument(),
    );
  });

  it("upload-another resets to idle", async () => {
    mockUpload.mockResolvedValue(SUCCESS_DOC);
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() =>
      screen.getByRole("button", { name: /upload another/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: /upload another/i }));
    expect(
      screen.getByRole("button", { name: /click to choose/i }),
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Loading state
  // -----------------------------------------------------------------------

  it("shows uploading state while request is in flight", async () => {
    let resolve: (doc: DocumentResponse) => void = () => {};
    mockUpload.mockImplementation(() => new Promise((r) => { resolve = r; }));
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() =>
      expect(screen.getByText("Uploading…")).toBeInTheDocument(),
    );
    resolve(SUCCESS_DOC);
  });

  it("upload button is disabled while uploading", async () => {
    let resolve: (doc: DocumentResponse) => void = () => {};
    mockUpload.mockImplementation(() => new Promise((r) => { resolve = r; }));
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /uploading/i })).toBeDisabled(),
    );
    resolve(SUCCESS_DOC);
  });

  // -----------------------------------------------------------------------
  // Unsupported type
  // -----------------------------------------------------------------------

  it("rejects unsupported file type with explicit message", () => {
    render(<UploadZone />);
    pickFile("photo.jpg", "image/jpeg");
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/\.jpg.*not supported/i);
    expect(alert).toHaveTextContent(/pdf.*docx.*txt/i);
  });

  it("unsupported type does not call uploadDocument", () => {
    render(<UploadZone />);
    pickFile("photo.jpg", "image/jpeg");
    expect(mockUpload).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Oversized file
  // -----------------------------------------------------------------------

  it("rejects oversized file with size in message", () => {
    render(<UploadZone />);
    pickFile("big.pdf", "application/pdf", 21 * 1024 * 1024);
    expect(screen.getByRole("alert")).toHaveTextContent(/20 mb/i);
  });

  it("oversized file does not call uploadDocument", () => {
    render(<UploadZone />);
    pickFile("big.pdf", "application/pdf", 21 * 1024 * 1024);
    expect(mockUpload).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Upload error
  // -----------------------------------------------------------------------

  it("shows explicit error message on upload failure", async () => {
    mockUpload.mockRejectedValue(new Error("Storage write failed."));
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Storage write failed."),
    );
  });

  it("passes backend error message through to UI", async () => {
    mockUpload.mockRejectedValue(
      new Error("File type 'image/jpeg' is not supported."),
    );
    render(<UploadZone />);
    pickFile("contract.pdf", "application/pdf");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "File type 'image/jpeg' is not supported.",
      ),
    );
  });
});
