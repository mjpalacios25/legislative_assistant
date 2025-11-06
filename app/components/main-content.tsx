import Config from "./config";
// import Header from "./Header";

export default function MainContent({
  children = <></>,
  config = <Config />,
}: {
  children?: React.ReactNode;
  config?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col">
      {/* <Header config={config} /> */}
      <main className="grid flex-1 gap-4 overflow-auto p-4 md:grid-cols-2 lg:grid-cols-3">
        <div
          className="relative hidden flex-col items-start gap-8 md:flex"
          x-chunk="dashboard-03-chunk-0"
        >
          <form className="grid w-full items-start gap-6">{config}</form>
        </div>
        {children}
      </main>
      <div />
    </div>
  );
}