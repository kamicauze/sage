'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Hammer, Search, BarChart3, Settings, Brain, Activity, Menu } from 'lucide-react';
import { useState } from 'react';

const brainNavigation = [
    { name: 'Brain', href: '/brain', icon: Brain },
    { name: 'Live', href: '/brain/live', icon: Activity },
];

const architectNavigation = [
    { name: 'Dash', href: '/', icon: Home },
    { name: 'Build', href: '/build', icon: Hammer },
    { name: 'Mem', href: '/memory', icon: Search },
    { name: 'Stats', href: '/stats', icon: BarChart3 },
];

export function BottomNav() {
    const pathname = usePathname();
    const isBrainPath = pathname.startsWith('/brain');
    const [showMenu, setShowMenu] = useState(false);

    // Toggle between Brain and Architect modes
    const toggleMode = () => {
        // Navigate to the root of the other mode
        // This part is handled by the links in the menu or direct actions
    };

    const navItems = isBrainPath ? brainNavigation : architectNavigation;

    return (
        <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white/5 border-t border-white/10 backdrop-blur-xl z-50 pb-safe">
            <div className="flex justify-around items-center h-16 px-2">
                {/* Navigation Items */}
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive ? 'text-white' : 'text-gray-300/70'
                                }`}
                        >
                            <Icon size={20} />
                            <span className="text-[10px] font-medium">{item.name}</span>
                        </Link>
                    );
                })}

                {/* Mode Switcher / Menu Trigger */}
                <button
                    onClick={() => setShowMenu(!showMenu)}
                    className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${showMenu ? 'text-white' : 'text-gray-300/70'
                        }`}
                >
                    <Menu size={20} />
                    <span className="text-[10px] font-medium">Menu</span>
                </button>
            </div>

            {/* Expanded Menu for Mode Switching and Extras */}
            {showMenu && (
                <div className="absolute bottom-16 left-0 right-0 bg-white/10 border-t border-white/10 p-4 shadow-2xl backdrop-blur-xl animate-in slide-in-from-bottom">
                    <div className="grid grid-cols-2 gap-4">
                        <Link
                            href="/"
                            onClick={() => setShowMenu(false)}
                            className={`p-4 rounded-2xl border border-white/10 flex flex-col items-center gap-2 ${!isBrainPath ? 'bg-white/15 border-white/20' : 'bg-white/5'
                                }`}
                        >
                            <Home size={24} className={!isBrainPath ? 'text-white' : 'text-gray-300/70'} />
                            <span className="font-medium">Architect Mode</span>
                        </Link>

                        <Link
                            href="/brain"
                            onClick={() => setShowMenu(false)}
                            className={`p-4 rounded-2xl border border-white/10 flex flex-col items-center gap-2 ${isBrainPath ? 'bg-white/15 border-white/20' : 'bg-white/5'
                                }`}
                        >
                            <Brain size={24} className={isBrainPath ? 'text-white' : 'text-gray-300/70'} />
                            <span className="font-medium">Brain Mode</span>
                        </Link>

                        <Link
                            href="/settings"
                            onClick={() => setShowMenu(false)}
                            className="col-span-2 p-3 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center gap-2 text-gray-200"
                        >
                            <Settings size={18} />
                            <span>Settings</span>
                        </Link>
                    </div>
                </div>
            )}
        </div>
    );
}
