import { Injectable, inject } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import {
  ApiClient,
  GetLabels$Params,
  ItemBarcodeCreate,
  ItemBarcodeLink,
  ItemBarcodeOut,
  ItemBarcodeUpdate,
  ScanResult,
  addItemBarcode,
  createItemBarcode,
  generateItemBarcode,
  getLabels,
  getScanResult,
  listItemBarcodes,
  updateItemBarcode,
  withRowVersion,
} from '@trishul/core-api';

export type { ItemBarcodeOut, ScanMatch, ScanResult } from '@trishul/core-api';

export type BarcodeType = ItemBarcodeOut['barcodeType'];
export type LabelRequest = GetLabels$Params;

export const BARCODE_TYPES: { value: BarcodeType; label: string }[] = [
  { value: 'EAN13', label: 'EAN-13 (13 digits)' },
  { value: 'EAN8', label: 'EAN-8 (8 digits)' },
  { value: 'UPCA', label: 'UPC-A (12 digits)' },
  { value: 'Code128', label: 'Code 128 (letters and digits)' },
  { value: 'QR', label: 'QR code' },
  { value: 'Other', label: 'Other' },
];

/** A likely type for a scanned value: 13 / 8 / 12 digits are retail barcodes, anything else Code 128. */
export function guessBarcodeType(value: string): BarcodeType {
  const text = value.trim();
  if (/^\d{13}$/.test(text)) return 'EAN13';
  if (/^\d{8}$/.test(text)) return 'EAN8';
  if (/^\d{12}$/.test(text)) return 'UPCA';
  return 'Code128';
}

/** Item barcodes (optional), the scan / find lookup and barcode labels (backend /inv/items/{id}/barcodes, /inv/scan, /inv/labels). */
@Injectable({ providedIn: 'root' })
export class BarcodeApi {
  private readonly api = inject(ApiClient);

  list(itemId: number): Observable<ItemBarcodeOut[]> {
    return this.api.call(listItemBarcodes, { itemId });
  }

  add(itemId: number, body: ItemBarcodeCreate): Observable<ItemBarcodeOut> {
    return this.api.call(addItemBarcode, { itemId, body });
  }

  /** An unknown barcode scanned on the scan screen, linked to an item there. */
  link(body: ItemBarcodeLink): Observable<ItemBarcodeOut> {
    return this.api.call(createItemBarcode, { body });
  }

  generate(itemId: number): Observable<ItemBarcodeOut> {
    return this.api.call(generateItemBarcode, { itemId });
  }

  update(
    barcode: ItemBarcodeOut,
    body: ItemBarcodeUpdate,
  ): Observable<ItemBarcodeOut> {
    return this.api.call(
      updateItemBarcode,
      { barcodeId: barcode.id, body },
      withRowVersion(barcode.rowVersion),
    );
  }

  scan(code: string, screen = 'scan'): Observable<ScanResult> {
    return this.api.call(getScanResult, { code, screen });
  }

  /**
   * Opens the label PDF in a new tab to print. The tab is opened first (a popup blocker only allows that
   * inside the click) and pointed at the PDF once it arrives; if the browser blocked it, the PDF is saved.
   */
  printLabels(request: LabelRequest): Subscription {
    const tab = window.open('', '_blank');
    return this.api.call(getLabels, request).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        if (tab) {
          tab.location.href = url;
        } else {
          const link = document.createElement('a');
          link.href = url;
          link.download = `${request.kind.toLowerCase()}-labels.pdf`;
          link.click();
        }
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      },
      error: () => tab?.close(),
    });
  }
}
