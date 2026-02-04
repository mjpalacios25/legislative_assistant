import MainContent from "../components/main-content";
import InfoPanel from "../components/info-panel";
import { Chat } from "../chat/Chat";

const ragFeatures = [
  {
    title: "Legislative Q&A",
    description:
      "Ask questions about legislative documents and get AI-powered answers grounded in actual bill text from the knowledge graph.",
  },
];

export default function Page() {
  return (
    <MainContent infoPanel={<InfoPanel features={ragFeatures} />}>
      <Chat />
    </MainContent>
  );
}
