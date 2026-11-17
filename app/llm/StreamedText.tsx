import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";

export default function StreamedText({
  text,
  isLoading = false,
}: {
  text: string;
  isLoading?: boolean;
}) {
  return (
    <div className="min-h-[20px]">
      {isLoading && text === "" ? (
        <PulsatingDot />
      ) : (
        <div className="prose">
          <ReactMarkdown remarkPlugins={[remarkBreaks]}>
            {text + (isLoading ? "  ⬤" : "")}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function PulsatingDot() {
  return <div className="h-2 w-2 animate-pulse-dot rounded-full bg-foreground"></div>;
}
