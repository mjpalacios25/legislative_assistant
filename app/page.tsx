import MainContent from "./components/main-content";
import InfoPanel from "./components/info-panel";
import { Chat } from "./chat/Chat";

const homeFeatures = [
  {
    title: "Legislative Research",
    description:
      "This assistant helps you research and understand legislative documents, bills, and policy.\n\nUsing a knowledge graph of legislation, responses are grounded in actual bill text to reduce hallucinations.",
    query: "What does HR 1234 propose?",
    response: "Summary of the bill's key provisions...",
  },
];

export default function Home() {
  return (
    <MainContent infoPanel={<InfoPanel features={homeFeatures} />}>
      <Chat />
    </MainContent>
  );
}
