import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/common/Button";
import { MeetingsTable } from "@/components/meetings/MeetingsTable";

export default function MeetingsPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Meetings"
        action={
          <Link href="/meetings/new">
            <Button variant="primary" size="md">
              + New Meeting
            </Button>
          </Link>
        }
      />
      <MeetingsTable />
    </div>
  );
}

