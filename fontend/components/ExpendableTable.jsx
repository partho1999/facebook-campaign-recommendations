import React, { useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Pause } from "lucide-react";
import ConfirmModal from "@/components/ConfirmModal";
import ActionModal from "@/components/ActionModal";
import { updateAdsetStatus } from "@/lib/api";

const ExpendableTable = ({ data }) => {
  const [selectedRecommendation, setSelectedRecommendation] = useState("");
  const [expandedRows, setExpandedRows] = useState([]);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [selectedAdsetId, setSelectedAdsetId] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: "asc" });
  const [adsetSortConfig, setAdsetSortConfig] = useState({});
  const [pausedAdsets, setPausedAdsets] = useState({}); // ✅ track paused state per adset

  const handlePauseAction = async (subId2) => {
    try {
      const response = await fetch(
        `https://app.wijte.me/api/adset/pause/${subId2}`,
        { method: "POST", headers: { "Content-Type": "application/json" } }
      );
      if (!response.ok) throw new Error(`Failed to pause adset ${subId2}`);
      await response.json();
      alert(`Adset ${subId2} paused successfully.`);

      try {
        const updatedAdset = await updateAdsetStatus(subId2, false);
        console.log("Adset updated:", updatedAdset);
      } catch (error) {
        console.error(error);
        console.log("Failed to update adset status");
      }

      // ✅ mark only this adset as paused
      setPausedAdsets((prev) => ({ ...prev, [subId2]: true }));
    } catch (error) {
      alert(`Failed to pause Adset ${subId2}`);
    }
  };

  const handleExpand = (campaignId) => {
    setExpandedRows((prev) =>
      prev.includes(campaignId)
        ? prev.filter((id) => id !== campaignId)
        : [...prev, campaignId]
    );
  };

  const isExpanded = (campaignId) => expandedRows.includes(campaignId);

  const handleSort = (key) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const handleAdsetSort = (campaignId, key) => {
    setAdsetSortConfig((prev) => {
      const current = prev[campaignId] || { key: null, direction: "asc" };
      const direction =
        current.key === key && current.direction === "asc" ? "desc" : "asc";
      return { ...prev, [campaignId]: { key, direction } };
    });
  };

  // Helper functions
  const getROIColor = (roi) => {
    if (roi >= 50) return "text-green-800";
    if (roi >= 20) return "text-green-500";
    if (roi > 0) return "text-green-300";
    if (roi <= -50) return "text-red-800";
    if (roi <= -20) return "text-red-500";
    return "text-red-300";
  };

  const getRecommendationColor = (recommendation) => {
    switch (recommendation) {
      case "PAUSE":
        return "text-red-600";
      case "INCREASE_BUDGET":
        return "text-green-600";
      case "KEEP_RUNNING":
        return "text-blue-600";
      case "OPTIMIZE":
        return "text-orange-600";
      default:
        return "text-gray-700";
    }
  };

  const getCpcRateColor = (rate) => {
    switch (rate) {
      case "STANDARD":
        return "text-blue-600";
      case "HIGH":
        return "text-red-600";
      case "LOW":
        return "text-green-600";
      default:
        return "text-gray-700";
    }
  };

  const getStatusColor = (status) => {
    if (status.toLowerCase() === "active") return "text-green-600";
    if (status.toLowerCase() === "paused") return "text-red-600";
    return "text-gray-700";
  };

  // Filter campaigns by recommendation
  const filteredData = data.filter((campaign) => {
    if (!selectedRecommendation) return true;
    return campaign.recommendation === selectedRecommendation;
  });

  // Sort campaigns
  const sortedData = [...filteredData];
  if (sortConfig.key) {
    sortedData.sort((a, b) => {
      const valA = a[sortConfig.key];
      const valB = b[sortConfig.key];
      if (typeof valA === "string")
        return sortConfig.direction === "asc"
          ? valA.localeCompare(valB)
          : valB.localeCompare(valA);
      return sortConfig.direction === "asc" ? valA - valB : valB - valA;
    });
  }

  const getRows = (campaign) => {
    const rows = [];

    // Campaign row
    rows.push(
      <TableRow
        key={campaign.id}
        className="cursor-pointer hover:bg-gray-100 border-b text-sm"
        onClick={() => handleExpand(campaign.id)}
      >
        <TableCell className="px-4 py-1 flex items-center text-left">
          <span
            className={`mr-2 transform transition-transform duration-200 ${
              isExpanded(campaign.id) ? "rotate-90" : ""
            }`}
          >
            &gt;
          </span>
          {campaign.sub_id_6}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">{campaign.sub_id_3}</TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.total_cost.toFixed(2)}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.total_revenue.toFixed(2)}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.total_profit.toFixed(2)}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">{campaign.total_clicks}</TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.total_cpc.toFixed(2)}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">{campaign.geo}</TableCell>
        <TableCell className="px-2 py-1 text-left">{campaign.country}</TableCell>
        <TableCell
          className={`px-2 py-1 text-left font-semibold ${getROIColor(
            campaign.total_roi
          )}`}
        >
          {campaign.total_roi.toFixed(2)}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.total_conversion_rate.toFixed(2)}
        </TableCell>
        <TableCell
          className={`px-2 py-1 text-left font-semibold ${getRecommendationColor(
            campaign.recommendation
          )}`}
        >
          {campaign.recommendation}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.recommendation_percentage}
        </TableCell>
        <TableCell className="px-2 py-1 text-left">
          {campaign.recommendation === "INCREASE_BUDGET" && (
            <div className="inline-block" onClick={(e) => e.stopPropagation()}>
              <ActionModal
                initialCount={campaign.recommendation_percentage}
                campaign_id={campaign.sub_id_3}
                recomendations={campaign.recommendation}
              />
            </div>
          )}
        </TableCell>
      </TableRow>
    );

    // Expanded adset header
    if (isExpanded(campaign.id)) {
      const adsetColumns = [
        { name: "Adset", key: "sub_id_5" },
        { name: "Recommendation", key: "recommendation" },
        { name: "Reason", key: "reason" },
        { name: "Suggestion", key: "suggestion" },
        { name: "Cost", key: "cost" },
        { name: "Revenue", key: "revenue" },
        { name: "Profit", key: "profit" },
        { name: "Clicks", key: "clicks" },
        { name: "CPC", key: "cpc" },
        { name: "GEO", key: "geo" },
        { name: "Country", key: "country" },
        { name: "CPC Rate", key: "cpc_rate" },
        { name: "ROI (%)", key: "roi_confirmed" },
        { name: "Conv. Rate", key: "conversion_rate" },
        { name: "Priority", key: "priority" },
        { name: "Status", key: "status" },
        { name: "Action", key: null },
      ];

      rows.push(
        <TableRow
          key={campaign.id + "-adset-header"}
          className="bg-gray-200 text-gray-800 text-xs font-medium border-b"
        >
          {adsetColumns.map((col, idx) => (
            <TableHead
              key={idx}
              className="px-2 py-1 text-left cursor-pointer"
              onClick={() => col.key && handleAdsetSort(campaign.id, col.key)}
            >
              {col.name}{" "}
              {adsetSortConfig[campaign.id]?.key === col.key
                ? adsetSortConfig[campaign.id].direction === "asc"
                  ? "↑"
                  : "↓"
                : ""}
            </TableHead>
          ))}
        </TableRow>
      );

      // Sort adsets
      let adsets = [...campaign.adset];
      const adsetSort = adsetSortConfig[campaign.id];
      if (adsetSort?.key) {
        adsets.sort((a, b) => {
          const valA = a[adsetSort.key];
          const valB = b[adsetSort.key];
          if (typeof valA === "number" && typeof valB === "number")
            return adsetSort.direction === "asc" ? valA - valB : valB - valA;
          if (typeof valA === "string" && typeof valB === "string")
            return adsetSort.direction === "asc"
              ? valA.localeCompare(valB)
              : valB.localeCompare(valA);
          return 0;
        });
      }

      adsets.forEach((ad) => {
        const isDisabled =
          pausedAdsets[ad.sub_id_2] || ad.status.toLowerCase() === "paused";

        rows.push(
          <TableRow
            key={ad.sub_id_2}
            className="bg-gray-50 text-xs text-gray-700 border-b"
          >
            <TableCell className="px-8 py-1 text-left">{ad.sub_id_5}</TableCell>
            <TableCell
              className={`px-2 py-1 text-left font-semibold ${getRecommendationColor(
                ad.recommendation
              )}`}
            >
              {ad.recommendation}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">{ad.reason}</TableCell>
            <TableCell className="px-2 py-1 text-left">{ad.suggestion}</TableCell>
            <TableCell className="px-2 py-1 text-left">
              {ad.cost.toFixed(2)}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">
              {ad.revenue.toFixed(2)}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">
              {ad.profit.toFixed(2)}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">{ad.clicks}</TableCell>
            <TableCell className="px-2 py-1 text-left">
              {ad.cpc.toFixed(2)}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">{ad.geo}</TableCell>
            <TableCell className="px-2 py-1 text-left">{ad.country}</TableCell>
            <TableCell
              className={`px-2 py-1 text-left font-semibold ${getCpcRateColor(
                ad.cpc_rate
              )}`}
            >
              {ad.cpc_rate}
            </TableCell>
            <TableCell
              className={`px-2 py-1 text-left font-semibold ${getROIColor(
                ad.roi_confirmed
              )}`}
            >
              {ad.roi_confirmed.toFixed(2)}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">
              {ad.conversion_rate.toFixed(2)}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">{ad.priority}</TableCell>
            <TableCell
              className={`px-2 py-1 text-left font-semibold ${
                getStatusColor(pausedAdsets[ad.sub_id_2] ? "paused" : ad.status)
              }`}
            >
              {pausedAdsets[ad.sub_id_2] ? "Paused" : ad.status}
            </TableCell>
            <TableCell className="px-2 py-1 text-left">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedAdsetId(ad.sub_id_2);
                  setShowConfirmModal(true);
                }}
                className={`text-destructive ${
                  isDisabled ? "opacity-50 cursor-not-allowed" : ""
                }`}
                disabled={isDisabled}
              >
                <Pause className="h-4 w-4" />
              </button>
            </TableCell>
          </TableRow>
        );
      });
    }

    return rows;
  };

  return (
    <Card className="w-full relative">
      <CardHeader>
        <CardTitle className="text-indigo-700 text-start">
          🧠 Campaign Recommendations
        </CardTitle>
        <CardDescription className="text-gray-500 text-start">
          Grouped by Campaign ID
        </CardDescription>
      </CardHeader>

      <CardContent>
        <div className="mb-4 flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-700">
            Filter by Recommendation:
          </span>
          {[
            "",
            "PAUSE",
            "INCREASE_BUDGET",
            "OPTIMIZE",
            "RESTRUCTURE",
            "KEEP_RUNNING",
            "REVIEW",
          ].map((rec) => (
            <button
              key={rec || "all"}
              onClick={() => setSelectedRecommendation(rec)}
              className={`px-3 py-1 text-sm rounded border ${
                selectedRecommendation === rec
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-gray-700 hover:bg-gray-100"
              }`}
            >
              {rec || "All"}
            </button>
          ))}
        </div>

        <div className="overflow-x-auto">
          <Table className="min-w-full border border-gray-200 text-sm">
            <TableHeader className="bg-gray-100">
              <TableRow>
                {[
                  { name: "Campaign", key: "sub_id_6" },
                  { name: "ID", key: "sub_id_3" },
                  { name: "Cost", key: "total_cost" },
                  { name: "Revenue", key: "total_revenue" },
                  { name: "Profit", key: "total_profit" },
                  { name: "Clicks", key: "total_clicks" },
                  { name: "CPC", key: "total_cpc" },
                  { name: "GEO", key: "geo" },
                  { name: "Country", key: "country" },
                  { name: "ROI (%)", key: "total_roi" },
                  { name: "Conv. Rate", key: "total_conversion_rate" },
                  { name: "Recommendation", key: "recommendation" },
                  { name: "Budget Change %", key: "recommendation_percentage" },
                  { name: "Action", key: null },
                ].map((col, idx) => (
                  <TableHead
                    key={idx}
                    className="px-2 py-1 text-left cursor-pointer"
                    onClick={() => col.key && handleSort(col.key)}
                  >
                    {col.name}{" "}
                    {sortConfig.key === col.key
                      ? sortConfig.direction === "asc"
                        ? "↑"
                        : "↓"
                      : ""}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>{sortedData.map((campaign) => getRows(campaign))}</TableBody>
          </Table>
        </div>
      </CardContent>

      <ConfirmModal
        open={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        onConfirm={() => {
          if (selectedAdsetId) {
            handlePauseAction(selectedAdsetId);
            setShowConfirmModal(false);
          }
        }}
      />
    </Card>
  );
};

export default ExpendableTable;
