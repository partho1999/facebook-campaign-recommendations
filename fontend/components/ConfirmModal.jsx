"use client";

import { Dialog, DialogContent, DialogHeader, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function ConfirmModal({ open, onClose, onConfirm }) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <h2 className="text-lg font-semibold">Do you want to pause this Adset?</h2>
        </DialogHeader>
        <DialogFooter className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onClose(false)}>
            No
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Yes, Pause
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
