"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChatCircle,
  Files,
  Microphone,
  Brain,
  Gear,
  ArrowLineLeft,
  ArrowLineRight,
  Scales,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useSidebarStore } from "@/stores/sidebar-store";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const NAV = [
  { href: "/workspace", icon: ChatCircle, label: "Workspace" },
  { href: "/documents", icon: Files, label: "Documents" },
  { href: "/voice", icon: Microphone, label: "Voice" },
  { href: "/memory", icon: Brain, label: "Memory" },
];

export function SidebarNav({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 p-2 flex-1">
      {NAV.map(({ href, icon: Icon, label }) => {
        const active = pathname.startsWith(href);
        const link = (
          <Link
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors",
              "hover:bg-secondary text-muted-foreground hover:text-foreground",
              active && "bg-secondary text-foreground",
              collapsed && "justify-center px-2"
            )}
          >
            <Icon size={18} weight={active ? "fill" : "regular"} />
            {!collapsed && <span className="text-sm font-medium">{label}</span>}
          </Link>
        );
        if (collapsed) {
          return (
            <Tooltip key={href}>
              <TooltipTrigger>{link}</TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          );
        }
        return <div key={href}>{link}</div>;
      })}
    </nav>
  );
}

export function SidebarDesktop() {
  const { collapsed, toggle } = useSidebarStore();

  return (
    <TooltipProvider>
      <aside
        className={cn(
          "flex flex-col border-r border-border bg-sidebar transition-all duration-150",
          collapsed ? "w-14" : "w-60"
        )}
      >
        <div className={cn(
          "flex items-center gap-2 px-4 py-4 border-b border-border",
          collapsed && "justify-center px-2"
        )}>
          <Scales size={20} weight="fill" className="text-primary flex-shrink-0" />
          {!collapsed && <span className="text-heading text-foreground">Juris</span>}
        </div>

        <SidebarNav collapsed={collapsed} />

        <div className="p-2 border-t border-border flex flex-col gap-1">
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger>
                <Link
                  href="/settings"
                  className="flex justify-center rounded-lg px-2 py-2 transition-colors hover:bg-secondary text-muted-foreground hover:text-foreground"
                >
                  <Gear size={18} />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">Settings</TooltipContent>
            </Tooltip>
          ) : (
            <Link
              href="/settings"
              className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-secondary text-muted-foreground hover:text-foreground"
            >
              <Gear size={18} />
              <span className="text-sm font-medium">Settings</span>
            </Link>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggle}
            className={cn(
              "w-full text-muted-foreground hover:text-foreground",
              collapsed ? "justify-center px-2" : "justify-start gap-3"
            )}
          >
            {collapsed
              ? <ArrowLineRight size={18} />
              : <><ArrowLineLeft size={18} /><span className="text-sm">Collapse</span></>
            }
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
