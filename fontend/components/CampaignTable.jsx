"use client"

import { useState, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table"
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function CampaignTable() {
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [hoursBack, setHoursBack] = useState(72)
  const [searchTerm, setSearchTerm] = useState("")

  useEffect(() => {
    const fetchPredictionData = async () => {
      setLoading(true)
      try {
        const url = `http://127.0.0.1:8000/api/prediction-run?hours_back=${hoursBack}`
        const res = await fetch(url)
        const data = await res.json()

        setResponse({
          ...data,
          status: res.status,
          timestamp: new Date().toISOString()
        })
      } catch (error) {
        setResponse({
          error: error instanceof Error ? error.message : "Unknown error occurred",
          timestamp: new Date().toISOString()
        })
      } finally {
        setLoading(false)
      }
    }

    fetchPredictionData()
    const intervalId = setInterval(fetchPredictionData, 3 * 60 * 60 * 1000) // every 3 hours

    return () => clearInterval(intervalId)
  }, [hoursBack])

  const formatCurrency = (value) =>
    value != null ? `$${value.toFixed(2)}` : "-"
  const formatPercentage = (value) =>
    value != null ? `${(value * 100).toFixed(2)}%` : "-"

  const getRecommendationColor = (recommendation) => {
    switch (recommendation) {
      case "INCREASE BUDGET":
        return "success"
      case "DECREASE BUDGET":
        return "destructive"
      case "KEEP BUDGET":
        return "outline"
      default:
        return "secondary"
    }
  }

  const getRecommendationIcon = (recommendation) => {
    switch (recommendation) {
      case "INCREASE BUDGET":
        return <ArrowUpRight size={14} />
      case "DECREASE BUDGET":
        return <ArrowDownRight size={14} />
      default:
        return <Minus size={14} />
    }
  }

  const filteredRecommendations = response?.data?.filter((rec) =>
    rec.campaign_name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || []

  return (
    <div className="p-4 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex gap-2">
          <Input
            type="number"
            value={hoursBack}
            onChange={(e) => setHoursBack(Number(e.target.value))}
            placeholder="Hours back"
            className="w-32"
          />
          <Input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search campaign"
          />
        </div>
        <Button
          onClick={() => {
            setLoading(true)
            fetch(`http://127.0.0.1:8000/api/prediction-run?hours_back=${hoursBack}`)
              .then((res) => res.json())
              .then((data) => {
                setResponse({
                  ...data,
                  status: 200,
                  timestamp: new Date().toISOString()
                })
              })
              .catch((err) =>
                setResponse({ error: err.message, timestamp: new Date().toISOString() })
              )
              .finally(() => setLoading(false))
          }}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {response?.error && (
        <div className="text-red-600 text-sm">{response.error}</div>
      )}

      <div className="rounded-md border max-h-[600px] overflow-y-auto">
        <Table>
          <TableHeader className="sticky top-0 bg-white z-10 shadow-sm">
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
                    <p className="text-sm text-gray-600 max-w-xs truncate" title={rec.campaign_name}>
                      {rec.campaign_name}
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
                <TableCell>{formatCurrency(rec.metrics.cost)}</TableCell>
                <TableCell>{formatCurrency(rec.metrics.revenue)}</TableCell>
                <TableCell className={rec.metrics.profit >= 0 ? "text-green-600" : "text-red-600"}>
                  {formatCurrency(rec.metrics.profit)}
                </TableCell>
                <TableCell>{rec.metrics.clicks}</TableCell>
                <TableCell>{formatPercentage(rec.metrics.conversion_rate)}</TableCell>
                <TableCell className={rec.metrics.roi >= 0 ? "text-green-600" : "text-red-600"}>
                  {formatPercentage(rec.metrics.roi)}
                </TableCell>
                <TableCell>{formatCurrency(rec.metrics.cpc)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
