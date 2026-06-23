import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { GoogleButton } from "../google-button";

describe("GoogleButton", () => {
  it("renders label", () => {
    render(<GoogleButton onClick={() => {}} />);
    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<GoogleButton onClick={onClick} />);
    fireEvent.click(screen.getByText("Continue with Google"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled when loading", () => {
    render(<GoogleButton onClick={() => {}} loading />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("is disabled when disabled prop set", () => {
    render(<GoogleButton onClick={() => {}} disabled />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("does not call onClick when disabled", () => {
    const onClick = vi.fn();
    render(<GoogleButton onClick={onClick} disabled />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
