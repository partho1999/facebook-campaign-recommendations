"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button"
import CampaignAccordion from "@/components/CampaignAccordion";
import TimeRange from "@/components/TimeRange";
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

const formatCurrency = (amount) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(amount)

const formatPercentage = (value) =>
  `${(value * 100).toFixed(2)}%`

const getRecommendationColor = (rec) => {
  switch (rec) {
    case "PAUSE":
      return "destructive"
    case "RESTRUCTURE":
      return "destructive"
    case "UNDER OBSERVATION":
      return "secondary"
    case "MONITOR":
      return "blue"
    case "OPTIMIZE":
      return "green"
    default:
      return "default"
  }
}

const getRecommendationIcon = (rec) => {
  switch (rec) {
    case "PAUSE":
      return <Pause className="h-4 w-4" />
    case "UNDER OBSERVATION":
    case "MONITOR":
      return <Eye className="h-4 w-4" />
    case "OPTIMIZE":
      return <Activity className="h-4 w-4" />
    default:
      return <Activity className="h-4 w-4" />
  }
}


export default function Page() {
  const [activeTab, setActiveTab] = useState("tab1");
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(true)
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [data, setData] = useState([]);

  console.log(startDate)
  console.log(endDate)

  console.log(activeTab)

  
  const handleSearch = async () => {
    if (!startDate || !endDate) {
      alert("Please select both start and end dates.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`https://adrecommend.waywisetech.com/api/predict-time-range/?start_date=${startDate}&end_date=${endDate}`);
      const result = await res.json();
      if (result.success) {
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
        const res = await fetch("https://adrecommend.waywisetech.com/api/prediction-run");
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
      <div className="max-w-7xl mx-auto space-y-8">
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
          <Card>
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
                ["Avg ROI", formatPercentage(summary.average_roi / 100), summary.average_roi >= 0 ? "text-green-600" : "text-red-600"],
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
        <div className="w-full flex flex-col items-center">
          {/* Tabs */}
          {!loading && response?.success && data.length > 0 && (
            <div role="tablist" className="flex border-b border-gray-200 space-x-4 mb-4">
              <button
                role="tab"
                onClick={() => setActiveTab("tab1")}
                className={`px-4 py-2 text-sm font-medium transition ${
                  activeTab === "tab1"
                    ? "text-blue-600 border-b-2 border-blue-500"
                    : "text-gray-600 hover:text-blue-600 hover:border-b-2 hover:border-blue-500"
                }`}
              >
                Live Recomandations
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
                <CampaignAccordion data={data} loading={loading} response={response} />
              )}
              {activeTab === "tab2" && (
                <>
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
                              onClick={handleSearch}
                              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                              >
                              Search
                              </button>
                          </div>
                          </div>
                    </CardContent>
                  </Card>
                  <CampaignAccordion data={data} loading={loading} response={response} />
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
