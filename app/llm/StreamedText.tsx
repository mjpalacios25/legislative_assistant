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
        <ReactMarkdown className="prose" remarkPlugins={[remarkBreaks]}>
          {text + (isLoading ? "  ⬤" : "")}
        </ReactMarkdown>
      )}
    </div>
  );
}

function PulsatingDot() {
  return <div className="h-2 w-2 animate-pulse rounded-full bg-black"></div>;
}
