"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button"
import CampaignAccordion from "@/components/CampaignAccordion";
import CampaignTable from "@/components/ExpendableTable";
import Navbar from "@/components/NavBar";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Skeleton
} from "@/components/ui/skeleton"

import {
  Eye,
  Pause,
  Activity,
  Clock,
  AlertCircle,
  BarChart3,
  Target,
} from "lucide-react"

import { getMe, authFetch } from "@/lib/api";

const formatCurrency = (amount) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(amount)

const formatPercentage = (value) =>
  `${(value * 100).toFixed(2)}%`

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export default function Page() {
  const [activeTab, setActiveTab] = useState("tab1");
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(true)
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [data, setData] = useState([]);
  const [user, setUser] = useState(null);


  useEffect(() => {
    const fetchUser = async () => {
      const user = await getMe();
      setUser(user);
    };
    fetchUser();
  }, []);

  const handleSearch = async () => {
    if (!startDate || !endDate) {
      alert("Please select both start and end dates.");
      return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);

    if (start >= end) {
      alert("Start date must be earlier than end date.");
      return;
    }


    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE_URL}/api/predict-date-range/?start_date=${startDate}&end_date=${endDate}`);
      const result = await res.json();
      if (result.success) {
        setResponse(result); 
        setData(result.data || []);
      } else {
        console.error("API error:", result.error || "Unknown error");
        setData([]);
      }
    } catch (error) {
      console.error("Fetch error:", error);
      setData([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/prediction-daily`);
        const resData = await res.json(); // ✅ Rename here
        setResponse(resData);
        setData(resData.data || []);      // ✅ Use same renamed variable
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10800000);
    return () => clearInterval(interval);
  }, []);

  // const data = response?.data || []
  
  const summary = response?.summary || {}

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6 dark:from-slate-900 dark:to-slate-950">
      <div className="space-y-8">
        {!loading && response?.success && (
          <Navbar />
        )}
        {/* Loading */}
        {loading && (
          <Card>
            <CardContent className="p-6">
              <div className="space-y-4">
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-40 w-full rounded-md" />
                <Skeleton className="h-80 w-full rounded-md" />
              </div>
            </CardContent>
          </Card>
        )}
        {/* Error */}
        {response?.error && (
          <Card className="border border-red-500 bg-red-50">
            <CardContent className="flex items-center space-x-2 p-4 text-red-700">
              <AlertCircle className="h-5 w-5" />
              <p className="font-medium">Error: {response.error}</p>
            </CardContent>
          </Card>
        )}
        {/* Summary */}
        {!loading && response?.success && Object.keys(summary).length > 0 && (
          <>
          
          <div className="text-center space-y-2">
            <h1 className="text-4xl font-bold text-gray-900">Ad Recommendation Dashboard</h1>
            <p className="text-gray-600">Monitor and optimize your advertising campaigns</p>
            <Button onClick={() => window.location.reload()} variant="outline" size="sm" className="mt-2">
              <Activity className="mr-2 h-4 w-4" />
              Refresh Data
            </Button>
          </div>
          <Card className="w-full">
            <CardHeader>
              <CardTitle className="text-blue-800">📊 Summary Statistics</CardTitle>
              <CardDescription className="text-gray-500">
                Key metrics over the selected time window
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6">
              {[
                ["Total Cost", formatCurrency(summary.total_cost)],
                ["Total Revenue", formatCurrency(summary.total_revenue)],
                ["Total Profit/Loss", formatCurrency(summary.total_profit), summary.total_profit >= 0 ? "text-green-600" : "text-red-600"],
                ["Total Clicks", summary.total_clicks],
                ["Total Conversions", summary.total_conversions],
                ["Total Adsets", summary.total_adset],
                ["Total ROI", formatPercentage(summary.total_roi / 100), summary.total_roi >= 0 ? "text-green-600" : "text-red-600"],
                ["Avg Conv. Rate", formatPercentage(summary.average_conversion_rate)],
              ].map(([label, value, color], idx) => (
                <div key={idx}>
                  <h4 className="text-sm font-medium text-gray-600">{label}</h4>
                  <p className={`text-lg font-semibold ${color ?? "text-slate-800"}`}>{value}</p>
                </div>
              ))}
              <div>
                <h4 className="text-sm font-medium text-gray-600">Priority Distribution</h4>
                <div className="flex flex-wrap gap-2 mt-2">
                  {Object.entries(summary.priority_distribution).map(([priority, count]) => (
                    <Badge key={priority} variant="outline" className="text-xs px-2 py-1 bg-slate-100 border-slate-300 text-slate-800">
                      P{priority}: {count}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
          </>
        )}
        <div className="w-full flex flex-col">
          {/* Tabs */}
          {!loading && response?.success && data.length > 0 && (
            <div role="tablist" className="flex justify-center border-b border-gray-200 space-x-4 mb-4">
              <button
                role="tab"
                onClick={() => {
                  setActiveTab("tab1");
                  window.location.reload();
                }}
                className={`px-4 py-2 text-sm font-medium transition ${
                  activeTab === "tab1"
                    ? "text-blue-600 border-b-2 border-blue-500"
                    : "text-gray-600 hover:text-blue-600 hover:border-b-2 hover:border-blue-500"
                }`}
              >
                Live Recommendations
              </button>
              <button
                role="tab"
                onClick={() => setActiveTab("tab2")}
                className={`px-4 py-2 text-sm font-medium transition ${
                  activeTab === "tab2"
                    ? "text-blue-600 border-b-2 border-blue-500"
                    : "text-gray-600 hover:text-blue-600 hover:border-b-2 hover:border-blue-500"
                }`}
              >
                Time Range
              </button>
            </div>
          )}

          {/* Tab Content */}
          {!loading && response?.success && data.length > 0 && (
            <div className="mt-4 text-center">
              {activeTab === "tab1" && (
                <>
                  <CampaignTable data={data} />
                  {/* <CampaignAccordion data={data} loading={loading} response={response} /> */}
                </>
                
              )}
              {activeTab === "tab2" && (
                <>
                  <Card className="w-full space-y-4 mb-4">
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
                              onClick={handleSearch}
                              disabled={loading}
                              className={`px-4 py-2 ${loading ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"} text-white rounded`}
                              >
                              Search
                              </button>
                          </div>
                          </div>
                    </CardContent>
                  </Card>
                  <CampaignTable data={data} />
                  {/* <CampaignAccordion data={data} loading={loading} response={response} /> */}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
