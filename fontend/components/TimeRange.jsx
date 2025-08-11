"use client";

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { useState, useEffect } from "react";

export default function Page() {
  const [activeTab, setActiveTab] = useState("tab1");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState([]);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState(""); // NEW: To handle input box separately

  console.log(startDate)
  console.log(endDate)
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("https://adrecommend.waywisetech.com/api/prediction-run");
        const json = await res.json();
        setResponse(json);
        setData(json?.data || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10800000); // 3 hours
    return () => clearInterval(interval);
  }, []);

  if (loading) return <p>Loading...</p>;

  // Filter data by date and search input
  const filteredData = data.filter(item => {
    const inDateRange =
      (!startDate || item.day >= startDate) &&
      (!endDate || item.day <= endDate);

    const matchesSearch =
      !searchQuery ||
      item.sub_id_6?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.sub_id_3?.toLowerCase().includes(searchQuery.toLowerCase());

    return inDateRange && matchesSearch;
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-indigo-700 text-start">Add Filter</CardTitle>
        <CardDescription className="text-gray-500 text-start">
          Grouped by Campaign ID
        </CardDescription>
      </CardHeader>

      <CardContent>
            {/* Filter Form */}
            <div className="flex flex-wrap items-end gap-4 mb-6">
            <div className="min-w-[150px]">
                <label className="block text-sm font-medium text-gray-700">Start Date</label>
                <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="w-full border px-2 py-1 rounded"
                />
            </div>
            <div className="min-w-[150px]">
                <label className="block text-sm font-medium text-gray-700">End Date</label>
                <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="w-full border px-2 py-1 rounded"
                />
            </div>
            <div className="shrink-0">
                <button
                onClick={() => setSearchQuery(searchInput)}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                Search
                </button>
            </div>
            </div>
      </CardContent>
    </Card>
  );
}
