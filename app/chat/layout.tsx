import Sidebar from "../components/sidebar";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid h-screen w-full pl-[56px]">
     
      <div className="flex-grow p-6 md:overflow-y-auto md:p-12">{children}</div>
    </div>
  );
}