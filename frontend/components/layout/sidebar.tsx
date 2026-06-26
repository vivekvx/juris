"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Gear,
  ArrowLineLeft,
  ArrowLineRight,
  Scales,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { NAV } from "@/lib/nav";
import { useSidebarStore } from "@/stores/sidebar-store";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { SidebarConversations } from "@/components/layout/sidebar-conversations";

function NavLink({
  href,
  icon: Icon,
  label,
  collapsed,
  active,
}: {
  href: string;
  icon: React.ComponentType<{ size?: number; weight?: "fill" | "regular" }>;
  label: string;
  collapsed: boolean;
  active: boolean;
}) {
  const link = (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-primary/10 text-foreground"
          : "text-muted-foreground hover:bg-secondary hover:text-foreground",
        collapsed && "justify-center px-2",
      )}
      aria-current={active ? "page" : undefined}
    >
      <Icon size={16} weight={active ? "fill" : "regular"} />
      {!collapsed && <span className="font-medium leading-none">{label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger>{link}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }
  return link;
}

function SidebarNav({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-0.5 p-2" aria-label="Main navigation">
      {NAV.map(({ href, icon, label }) => (
        <NavLink
          key={href}
          href={href}
          icon={icon}
          label={label}
          collapsed={collapsed}
          active={pathname.startsWith(href)}
        />
      ))}
    </nav>
  );
}

function SidebarFooter({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  const { toggle } = useSidebarStore();

  return (
    <div className="p-2 border-t border-border flex flex-col gap-0.5 flex-shrink-0">
      <NavLink
        href="/settings"
        icon={Gear}
        label="Settings"
        collapsed={collapsed}
        active={pathname.startsWith("/settings")}
      />
      <button
        type="button"
        onClick={toggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className={cn(
          "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
          "text-muted-foreground hover:bg-secondary hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          collapsed && "justify-center px-2",
        )}
      >
        {collapsed
          ? <ArrowLineRight size={16} />
          : <><ArrowLineLeft size={16} /><span className="font-medium leading-none">Collapse</span></>
        }
      </button>
    </div>
  );
}

export function SidebarDesktop() {
  const { collapsed } = useSidebarStore();

  return (
    <TooltipProvider>
      <aside
        className={cn(
          "flex flex-col border-r border-border bg-sidebar transition-all duration-200",
          collapsed ? "w-[52px]" : "w-[220px]",
        )}
        aria-label="Sidebar"
      >
        <div className={cn(
          "flex items-center gap-2 px-3 py-3 border-b border-border flex-shrink-0",
          collapsed && "justify-center",
        )}>
          <Scales size={18} weight="fill" className="text-primary flex-shrink-0" />
          {!collapsed && (
            <span className="text-sm font-semibold tracking-tight text-foreground">Juris</span>
          )}
        </div>

        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          <SidebarNav collapsed={collapsed} />
          {!collapsed && <SidebarConversations />}
          {collapsed && <div className="flex-1" />}
        </div>

        <SidebarFooter collapsed={collapsed} />
      </aside>
    </TooltipProvider>
  );
}
