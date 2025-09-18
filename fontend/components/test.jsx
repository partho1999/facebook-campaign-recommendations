"use client";

import { useEffect, useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatPercentage } from "@/lib/utils";
import { Pause, Eye, Activity } from "lucide-react";
import ActionModal from "@/components/ActionModal";
import ConfirmModal from "@/components/ConfirmModal";

const getRecommendationColor = (rec) => {
  switch (rec) {
    case "PAUSE":
    case "RESTRUCTURE":
      return "destructive";
    case "UNDER OBSERVATION":
      return "secondary";
    case "INCREASE_BUDGET":
      return "green";
    case "KEEP_RUNNING":
      return "orange";
    case "MONITOR":
      return "blue";
    case "OPTIMIZE":
      return "yellow";
    default:
      return "default";
  }
};

const getCpcRateColor = (rec) => {
  switch (rec) {
    case "HIGH":
    case "RESTRUCTURE":
      return "destructive";
    case "UNDER OBSERVATION":
      return "secondary";
    case "STANDARD":
      return "blue";
    case "LOW":
      return "green";
    default:
      return "default";
  }
};

const getRecommendationIcon = (rec) => {
  switch (rec) {
    case "PAUSE":
      return <Pause className="h-4 w-4" />;
    case "UNDER OBSERVATION":
    case "MONITOR":
      return <Eye className="h-4 w-4" />;
    case "OPTIMIZE":
    default:
      return <Activity className="h-4 w-4" />;
  }
};

export default function CampaignAccordion({
  data = [],
  loading = false,
  response = {},
}) {
  const [selectedRecommendation, setSelectedRecommendation] = useState("");
  const [openItems, setOpenItems] = useState([]);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [selectedAdsetId, setSelectedAdsetId] = useState(null);
  const [hoveredCampaign, setHoveredCampaign] = useState(null);
  const [hoverModalOpen, setHoverModalOpen] = useState(false);

  useEffect(() => {
    if (data?.length > 0) {
      setOpenItems(data.slice(0, 4).map((item) => item.id?.toString()));
    }
  }, [data]);

  // Body scroll lock when hover modal is open
  useEffect(() => {
    if (hoverModalOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [hoverModalOpen]);

  const handlePauseAction = async (subId2) => {
    try {
      const response = await fetch(
        `https://app.wijte.me/api/adset/pause/${subId2}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) throw new Error(`Failed to pause adset ${subId2}`);

      await response.json();
      alert(`Adset ${subId2} paused successfully.`);
    } catch (error) {
      alert(`Failed to pause Adset ${subId2}`);
    }
  };

  if (loading || !response?.success || data.length === 0) return null;

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
        

        
      </CardContent>

      

     
    </Card>
  );
}
