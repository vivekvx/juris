import { Scales } from "@phosphor-icons/react/dist/ssr";

export function EmptyConversation() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <Scales size={32} className="text-muted-foreground" weight="thin" />
      <div>
        <p className="text-subhead text-foreground">How can Juris help?</p>
        <p className="text-caption text-muted-foreground mt-1">
          Ask a legal question in English, Hindi, Kannada, Tamil, or Telugu
        </p>
      </div>
    </div>
  );
}
