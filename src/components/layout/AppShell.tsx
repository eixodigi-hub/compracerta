import type { ReactNode } from "react";
import { TopNav } from "./TopNav";
import { BottomNav } from "./BottomNav";
import { CitySelectGate } from "./CitySelectGate";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <CitySelectGate>
      <div className="flex min-h-screen flex-col bg-background text-foreground">
        <TopNav />
        <main className="flex-1 pb-20 md:pb-0">{children}</main>
        <BottomNav />
      </div>
    </CitySelectGate>
  );
}
