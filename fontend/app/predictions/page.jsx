"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, Server, Activity, TrendingUp, Eye, Pause, DollarSign, BarChart3, Target, MousePointer, Clock } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import Link from "next/link"

export default function AdRecDashboard() {
  const [hoursBack, setHoursBack] = useState("24")
  const [filter, setFilter] = useState("ALL")
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPredictionData = async () => {
      setLoading(true)
      try {
        const url = `http://127.0.0.1:8000/api/predictions`

        const res = await fetch(url, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        })

        const data = await res.json()

        setResponse({
          ...data,
          status: res.status,
          timestamp: new Date().toISOString(),
        })
      } catch (error) {
        setResponse({
          error: error instanceof Error ? error.message : "Unknown error occurred",
          timestamp: new Date().toISOString(),
        })
      } finally {
        setLoading(false)
      }
    }

    fetchPredictionData()
  }, [hoursBack])

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(amount)
  }

  const formatPercentage = (value) => {
    return `${(value * 100).toFixed(2)}%`
  }

  const getRecommendationColor = (recommendation) => {
    switch (recommendation) {
      case "PAUSE":
        return "destructive"
      case "UNDER OBSERVATION":
        return "secondary"
      default:
        return "default"
    }
  }

  const getRecommendationIcon = (recommendation) => {
    switch (recommendation) {
      case "PAUSE":
        return <Pause className="h-4 w-4" />
      case "UNDER OBSERVATION":
        return <Eye className="h-4 w-4" />
      default:
        return <Activity className="h-4 w-4" />
    }
  }

  const recommendations = response?.recommendations || []

  const filteredRecommendations =
    filter === "ALL" ? recommendations : recommendations.filter((r) => r.recommendation === filter)

  const totalCost = recommendations.reduce((sum, r) => sum + r.cost, 0)
  const totalRevenue = recommendations.reduce((sum, r) => sum + r.revenue, 0)
  const totalProfit = recommendations.reduce((sum, r) => sum + r.profit, 0)
  const totalClicks = recommendations.reduce((sum, r) => sum + r.clicks, 0)

  const uniqueRecommendationTypes = [...new Set(recommendations.map(r => r.recommendation))]

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="text-center space-y-2">
          <div className="flex justify-center gap-4 mb-4">
            <Link href="/">
              <Button variant="outline" size="sm">
                <BarChart3 className="mr-2 h-4 w-4" />
                Live
              </Button>
            </Link>
            <Link href="/predictions">
              <Button variant="default" size="sm">
                <Target className="mr-2 h-4 w-4" />
                24 Hours
              </Button>
            </Link>
          </div>
          <h1 className="text-4xl font-bold text-gray-900">Ad Recommendation Dashboard</h1>
          <p className="text-gray-600">Monitor and optimize your advertising campaigns</p>
          <Button onClick={() => window.location.reload()} variant="outline" size="sm" className="mt-2">
            <Activity className="mr-2 h-4 w-4" />
            Refresh Data
          </Button>
        </div>

        {loading && (
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-center space-x-2">
                <Clock className="h-6 w-6 animate-spin" />
                <p>Loading campaign recommendations...</p>
              </div>
            </CardContent>
          </Card>
        )}

        {response?.error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>Error:</strong> {response.error}
            </AlertDescription>
          </Alert>
        )}

        {response?.success && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center space-x-2">
                    <Server className="h-8 w-8 text-blue-600" />
                    <div>
                      <p className="text-2xl font-bold">{recommendations.length}</p>
                      <p className="text-sm text-gray-600">Total Campaigns</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center space-x-2">
                    <DollarSign className="h-8 w-8 text-green-600" />
                    <div>
                      <p className="text-2xl font-bold">{formatCurrency(totalCost)}</p>
                      <p className="text-sm text-gray-600">Total Cost</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="h-8 w-8 text-purple-600" />
                    <div>
                      <p className="text-2xl font-bold">{formatCurrency(totalProfit)}</p>
                      <p className="text-sm text-gray-600">Total Profit</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center space-x-2">
                    <MousePointer className="h-8 w-8 text-orange-600" />
                    <div>
                      <p className="text-2xl font-bold">{totalClicks}</p>
                      <p className="text-sm text-gray-600">Total Clicks</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Campaign Recommendations</CardTitle>
                <CardDescription>Filter and view detailed campaign recommendations</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2 mb-4 flex-wrap">
                  <Button variant={filter === "ALL" ? "default" : "outline"} size="sm" onClick={() => setFilter("ALL")}>
                    All ({recommendations.length})
                  </Button>
                  {uniqueRecommendationTypes.map((rec) => (
                    <Button
                      key={rec}
                      variant={filter === rec ? "default" : "outline"}
                      size="sm"
                      onClick={() => setFilter(rec)}
                    >
                      {rec}
                    </Button>
                  ))}
                </div>

                <div className="rounded-md border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Campaign</TableHead>
                        <TableHead>Recommendation</TableHead>
                        <TableHead>Cost</TableHead>
                        <TableHead>Revenue</TableHead>
                        <TableHead>Profit</TableHead>
                        <TableHead>Clicks</TableHead>
                        <TableHead>Conv. Rate</TableHead>
                        <TableHead>ROI</TableHead>
                        <TableHead>CPC</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredRecommendations.map((rec) => (
                        <TableRow key={rec.campaign_id}>
                          <TableCell>
                            <div>
                              <p className="font-medium">ID: {rec.campaign_id}</p>
                              <p className="text-sm text-gray-600 max-w-xs truncate" title={rec.campaign}>
                                {rec.campaign}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={getRecommendationColor(rec.recommendation)}
                              className="flex items-center gap-1 w-fit"
                            >
                              {getRecommendationIcon(rec.recommendation)}
                              {rec.recommendation}
                            </Badge>
                          </TableCell>
                          <TableCell>{formatCurrency(rec.cost)}</TableCell>
                          <TableCell>{formatCurrency(rec.revenue)}</TableCell>
                          <TableCell className={rec.profit >= 0 ? "text-green-600" : "text-red-600"}>
                            {formatCurrency(rec.profit)}
                          </TableCell>
                          <TableCell>{rec.clicks}</TableCell>
                          <TableCell>{formatPercentage(rec.conversion_rate)}</TableCell>
                          <TableCell className={rec.roi >= 0 ? "text-green-600" : "text-red-600"}>
                            {formatPercentage(rec.roi)}
                          </TableCell>
                          <TableCell>{formatCurrency(rec.cpc)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
