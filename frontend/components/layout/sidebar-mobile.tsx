"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { List, Scales, Gear } from "@phosphor-icons/react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NAV } from "@/lib/nav";
import { SidebarConversations } from "@/components/layout/sidebar-conversations";

const NAV_MOBILE = [...NAV, { href: "/settings", icon: Gear, label: "Settings" }];

export function SidebarMobile() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-2.5 left-2.5 z-40 h-8 w-8 text-muted-foreground hover:text-foreground"
        aria-label="Open navigation"
      >
        <List size={18} />
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-[220px] p-0 flex flex-col">
          <SheetHeader className="px-3 py-3 border-b border-border flex-shrink-0">
            <SheetTitle className="flex items-center gap-2">
              <Scales size={18} weight="fill" className="text-primary" />
              <span className="text-sm font-semibold tracking-tight text-foreground">Juris</span>
            </SheetTitle>
          </SheetHeader>

          <nav className="flex flex-col gap-0.5 p-2 flex-shrink-0" aria-label="Main navigation">
            {NAV_MOBILE.map(({ href, icon: Icon, label }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "bg-primary/10 text-foreground"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                  )}
                >
                  <Icon size={16} weight={active ? "fill" : "regular"} />
                  <span className="font-medium leading-none">{label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="flex-1 min-h-0 overflow-hidden border-t border-border">
            <SidebarConversations />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
