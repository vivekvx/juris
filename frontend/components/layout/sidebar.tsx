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
import { useUIStore } from "@/stores/ui";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const NAV = [
  { href: "/workspace", icon: ChatCircle, label: "Workspace" },
  { href: "/documents", icon: Files, label: "Documents" },
  { href: "/voice", icon: Microphone, label: "Voice" },
  { href: "/memory", icon: Brain, label: "Memory" },
];

interface SidebarProps {
  collapsed: boolean;
}

function NavItem({ href, icon: Icon, label, collapsed }: { href: string; icon: React.ElementType; label: string; collapsed: boolean }) {
  const pathname = usePathname();
  const active = pathname.startsWith(href);

  const inner = (
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
      <Tooltip>
        <TooltipTrigger>{inner}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }
  return inner;
}

export function Sidebar({ collapsed }: SidebarProps) {
  const { toggleSidebar } = useUIStore();

  return (
    <TooltipProvider>
      <aside
        className={cn(
          "flex flex-col border-r border-border bg-sidebar transition-all duration-200",
          collapsed ? "w-14" : "w-60"
        )}
      >
        {/* Logo */}
        <div className={cn("flex items-center gap-2 px-4 py-4 border-b border-border", collapsed && "justify-center px-2")}>
          <Scales size={20} weight="fill" className="text-primary flex-shrink-0" />
          {!collapsed && <span className="text-heading text-foreground">Juris</span>}
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 p-2 flex-1">
          {NAV.map((item) => (
            <NavItem key={item.href} {...item} collapsed={collapsed} />
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-2 border-t border-border flex flex-col gap-1">
          <NavItem href="/settings" icon={Gear} label="Settings" collapsed={collapsed} />
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className={cn("w-full justify-start gap-3 text-muted-foreground", collapsed && "justify-center px-2")}
          >
            {collapsed ? <ArrowLineRight size={18} /> : <><ArrowLineLeft size={18} /><span className="text-sm">Collapse</span></>}
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
