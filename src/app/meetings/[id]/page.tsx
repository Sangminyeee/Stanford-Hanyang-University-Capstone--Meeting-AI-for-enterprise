"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { MeetingTabs } from "@/components/meetings/MeetingTabs";
import { MeetingOverviewSection } from "@/components/meetings/MeetingOverviewSection";
import { MeetingPrepSection } from "@/components/meetings/MeetingPrepSection";
import { MeetingOutcomesSection } from "@/components/meetings/MeetingOutcomesSection";

type TabType = "overview" | "prep" | "live" | "outcomes" | "patterns";

export default function MeetingDetailPage() {
  const [activeTab, setActiveTab] = useState<TabType>("overview");

  const renderTabContent = () => {
    switch (activeTab) {
      case "overview":
        return <MeetingOverviewSection />;
      case "prep":
        return <MeetingPrepSection />;
      case "live":
        return (
          <Card className="p-12 text-center">
            <p className="text-slate-500">Live view coming soon</p>
          </Card>
        );
      case "outcomes":
        return <MeetingOutcomesSection />;
      case "patterns":
        return (
          <Card className="p-12 text-center">
            <p className="text-slate-500">Pattern analysis coming soon</p>
          </Card>
        );
      default:
        return <MeetingOverviewSection />;
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Meetings"
        action={
          <Button variant="primary" size="md">
            + New Meeting
          </Button>
        }
      />
      
      <Card className="p-0">
        <div className="p-6">
          <MeetingTabs activeTab={activeTab} onTabChange={setActiveTab} />
        </div>
        <div className="px-6 pb-6">
          {renderTabContent()}
        </div>
      </Card>
    </div>
  );
}

