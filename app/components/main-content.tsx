import Header from "./Header";

export default function MainContent({
  children = <></>,
  infoPanel,
}: {
  children?: React.ReactNode;
  infoPanel?: React.ReactNode;
}) {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {infoPanel}
        <main className="flex-1 overflow-auto bg-muted/30 p-4">
          {children}
        </main>
      </div>
    </div>
  );
}
