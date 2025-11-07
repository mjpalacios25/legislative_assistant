import MainContent from "../components/main-content";
import ContentContainer from "../components/content-container";
import Completion from "../completion/completion";
import Query from "../completion/query";
import Config from "../components/config";
import { Content } from "next/font/google";


export default function Page() {
    const description = (
    <p>
      The Chat feature, popularized by ChatGPT, utilizes a language model to
      engage in text-based dialogue.
      <br />
      <br />
      It's a flexible tool that can be adapted for multiple use cases:
      <br />
      - simulate interactive narratives or role-playing scenarios
      <br />
      - provide learning assistance through Q&A sessions
      <br />
      - serve as a platform for brainstorming or idea generation
      <br />
      ...and much more.
      <br />
      <br />
      <b>User:</b> Can you explain the theory of relativity?
      <br />
      <b>Assistant:</b> Sure, the theory of relativity, proposed by Albert
      Einstein, encompasses two interrelated theories: special relativity and
      general relativity...
    </p>
    )

    const config = <Config title="Chat" description= {description} />
  return (
    <MainContent config= {config} >
      <ContentContainer></ContentContainer>
        {/* <Query /> */}
    </MainContent>
  )
  
}   