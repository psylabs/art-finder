import { NavLink, Route, Routes } from "react-router-dom"

import { AppPage } from "@/pages/AppPage"
import { HelpPage } from "@/pages/HelpPage"
import { cn } from "@/lib/utils"
import { NavigationMenu, NavigationMenuItem, NavigationMenuLink, NavigationMenuList } from "@/components/ui/navigation-menu"

const navItems = [
  { to: "/", label: "App" },
  { to: "/help", label: "Help" },
]

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b bg-background/95 backdrop-blur">
        <div className="flex w-full flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" aria-hidden="true" className="h-7 w-auto object-contain" />
            <h1 className="text-xl font-semibold">Art Findr</h1>
          </div>

          <NavigationMenu>
            <NavigationMenuList className="gap-2">
              {navItems.map((item) => (
                <NavigationMenuItem key={item.to}>
                  <NavigationMenuLink asChild>
                    <NavLink
                      to={item.to}
                      end={item.to === "/"}
                      className={({ isActive }) =>
                        cn(
                          "inline-flex items-center rounded-sm px-3 py-2 text-sm font-medium transition-colors",
                          isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                        )
                      }
                    >
                      {item.label}
                    </NavLink>
                  </NavigationMenuLink>
                </NavigationMenuItem>
              ))}
            </NavigationMenuList>
          </NavigationMenu>
        </div>
      </header>

      <main className="w-full px-4 py-4 md:px-6">
        <Routes>
          <Route path="/" element={<AppPage />} />
          <Route path="/help" element={<HelpPage />} />
        </Routes>
      </main>
    </div>
  )
}
