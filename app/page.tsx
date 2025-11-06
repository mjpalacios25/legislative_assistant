
// import Image from "next/image";
import MainContent from "./components/main-content";
import ContentContainer from "./components/content-container";
import Config from "./components/config";
// import { Button } from "./components/button";
// import { Input } from "./components/input";
// import StreamedText  from "./llm/StreamedText";
// import { useCompletion } from "./completion/useCompletion";
// import { Message } from "./llm/types";
import Sidebar from "./components/sidebar";
import Completion from "./completion/completion";
// import Query from "./completion/query";
import { QueryClient ,QueryClientProvider } from "@tanstack/react-query";


const queryClient = new QueryClient();

export default function Home() {
  
  return (
    <QueryClientProvider client={queryClient}>
    <div className="grid h-screen w-full pl-[56px]">
      {/* <MainContent>
        <ContentContainer>
          <Completion />
        </ContentContainer>
      </MainContent> */}
      <div className="flex flex-col">
      {/* <Header config={config} /> */}
        <main className="grid flex-1 gap-4 overflow-auto p-4 md:grid-cols-2 lg:grid-cols-3">
          <div
            className="relative hidden flex-col items-start gap-8 md:flex"
            x-chunk="dashboard-03-chunk-0"
          >
            <form className="grid w-full items-start gap-6">
              <fieldset className="grid gap-6 rounded-lg border p-4">
                <legend className="-ml-1 px-1 text-sm font-medium">something</legend>
                that works
              </fieldset>

            </form>
          </div>
          {/* {children} */}
        </main>
      
      </div>
      
      
    </div>
    </QueryClientProvider>
  );
}
