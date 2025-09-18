"use client";

import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export default function Navbar() {
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const handleLogout = async () => {
    try {
      const accessToken = localStorage.getItem("access"); // adjust if stored elsewhere
      const refreshToken = localStorage.getItem("refresh");
      console.log("accessToken", accessToken);
      console.log("refreshToken", refreshToken);

      const response = await fetch(`${API_BASE_URL}/auth/logout/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      if (!response.ok) throw new Error("Logout failed");

      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      window.location.href = window.location.origin; // redirect after logout
    } catch (error) {
      console.error("Logout error:", error);
    }
  };

  return (
    <nav className="w-full bg-white shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-4 py-2">
        {/* Left Brand */}
        <div className="flex items-center">
          <a
            href="/predictions"
            className="text-xl font-semibold text-gray-800 hover:text-gray-900"
          >
            Recom
          </a>
        </div>

        {/* Right Side */}
        <div className="flex items-center gap-3">
          
          {/* Avatar Dropdown */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center justify-center w-10 h-10 rounded-full overflow-hidden border hover:ring-2 hover:ring-blue-500"
            >
              <img
                src="https://img.daisyui.com/images/stock/photo-1534528741775-53994a69daeb.webp"
                alt="User avatar"
                className="object-cover w-full h-full"
              />
            </button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <ul className="absolute right-0 mt-2 w-48 bg-white border rounded-lg shadow-lg">
                <li>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 hover:bg-gray-100 rounded-b-lg"
                  >
                    Logout
                  </button>
                </li>
              </ul>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
