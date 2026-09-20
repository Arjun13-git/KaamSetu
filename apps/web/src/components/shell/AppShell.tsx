import Link from "next/link";
import { Plus } from "lucide-react";
import { Suspense } from "react";

import { buttonClass } from "@/components/ui/Button";
import { ApiStatusPill } from "./ApiStatusPill";
import { Logo } from "./Logo";
import { NavLinks } from "./NavLinks";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only rounded-lg bg-surface px-4 py-2 text-sm font-medium shadow-pop focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur supports-[backdrop-filter]:bg-surface/80">
        <div className="mx-auto flex h-14 w-full max-w-[1440px] items-center gap-2 px-3 sm:gap-4 sm:px-6">
          <Link href="/" aria-label="KaamSetu home" className="shrink-0">
            <Logo />
          </Link>
          <div className="min-w-0 flex-1 overflow-x-auto scroll-thin">
            <NavLinks />
          </div>
          <Suspense fallback={null}>
            <ApiStatusPill />
          </Suspense>
          <Link href="/intake" className={buttonClass("primary", "md", "shrink-0 px-3 sm:px-4")}>
            <Plus className="size-4" aria-hidden />
            <span className="hidden sm:inline">New request</span>
            <span className="sm:hidden">New</span>
          </Link>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 focus:outline-none sm:px-6">{children}</main>
    </div>
  );
}
