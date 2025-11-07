
// import Image from "next/image";
import MainContent from "./components/main-content";
import ContentContainer from "./components/content-container";
import Config from "./components/config";
import Completion from "./completion/completion";
// import { Button } from "./components/button";
// import { Input } from "./components/input";
// import StreamedText  from "./llm/StreamedText";
// import { useCompletion } from "./completion/useCompletion";
// import { Message } from "./llm/types";


export default function Home() {
  
  return (
  
    <MainContent>
      <ContentContainer>
        <Completion />
      </ContentContainer>
    </MainContent>
      


  );
}
