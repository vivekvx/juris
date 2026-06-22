"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { List, Scales, ChatCircle, Files, Microphone, Brain, Gear } from "@phosphor-icons/react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/workspace", icon: ChatCircle, label: "Workspace" },
  { href: "/documents", icon: Files, label: "Documents" },
  { href: "/voice", icon: Microphone, label: "Voice" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/settings", icon: Gear, label: "Settings" },
];

export function SidebarMobile() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-3 left-3 z-40 text-muted-foreground"
        aria-label="Open menu"
      >
        <List size={20} />
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-60 p-0">
          <SheetHeader className="px-4 py-4 border-b border-border">
            <SheetTitle className="flex items-center gap-2">
              <Scales size={20} weight="fill" className="text-primary" />
              <span className="text-heading">Juris</span>
            </SheetTitle>
          </SheetHeader>
          <nav className="flex flex-col gap-1 p-2">
            {NAV.map(({ href, icon: Icon, label }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors",
                    "hover:bg-secondary text-muted-foreground hover:text-foreground",
                    active && "bg-secondary text-foreground"
                  )}
                >
                  <Icon size={18} weight={active ? "fill" : "regular"} />
                  <span className="text-sm font-medium">{label}</span>
                </Link>
              );
            })}
          </nav>
        </SheetContent>
      </Sheet>
    </>
  );
}
