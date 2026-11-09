import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';

/** A box to sign in with a finger or mouse. `toPng()` gives the drawing, or null if nothing was drawn. */
@Component({
  selector: 'trishul-signature-pad',
  imports: [MatButton, MatIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <canvas
      #canvas
      class="pad"
      width="600"
      height="200"
      [class.disabled]="disabled()"
      aria-label="Customer signature"
      (pointerdown)="begin($event)"
      (pointermove)="draw($event)"
      (pointerup)="end()"
      (pointerleave)="end()"
    ></canvas>
    <div class="bar">
      <span class="muted">{{
        signed() ? 'Signature drawn' : 'Sign inside the box'
      }}</span>
      <button
        mat-button
        type="button"
        [disabled]="disabled() || !signed()"
        (click)="clear()"
      >
        <mat-icon>ink_eraser</mat-icon> Clear
      </button>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .pad {
      width: 100%;
      max-width: 36rem;
      aspect-ratio: 3 / 1;
      border: 1px dashed var(--mat-sys-outline);
      border-radius: var(--mat-sys-corner-medium);
      background: #fff;
      touch-action: none;
      cursor: crosshair;
    }
    .pad.disabled {
      opacity: 0.5;
      pointer-events: none;
    }
    .bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      max-width: 36rem;
    }
    .muted {
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class SignaturePad {
  readonly disabled = input(false);
  protected readonly signed = signal(false);
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private drawing = false;

  protected begin(event: PointerEvent): void {
    if (this.disabled()) return;
    this.drawing = true;
    const ctx = this.context();
    const { x, y } = this.point(event);
    ctx.beginPath();
    ctx.moveTo(x, y);
    this.canvas().nativeElement.setPointerCapture(event.pointerId);
  }

  protected draw(event: PointerEvent): void {
    if (!this.drawing) return;
    const ctx = this.context();
    const { x, y } = this.point(event);
    ctx.lineTo(x, y);
    ctx.stroke();
    this.signed.set(true);
  }

  protected end(): void {
    this.drawing = false;
  }

  clear(): void {
    const el = this.canvas().nativeElement;
    this.context().clearRect(0, 0, el.width, el.height);
    this.signed.set(false);
  }

  /** True when something was drawn since the last clear. */
  hasInk(): boolean {
    return this.signed();
  }

  toPng(): Promise<Blob | null> {
    if (!this.signed()) return Promise.resolve(null);
    return new Promise((resolve) =>
      this.canvas().nativeElement.toBlob((blob) => resolve(blob), 'image/png'),
    );
  }

  private context(): CanvasRenderingContext2D {
    const ctx = this.canvas().nativeElement.getContext('2d');
    if (!ctx) throw new Error('Canvas is not available');
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#111';
    return ctx;
  }

  private point(event: PointerEvent): { x: number; y: number } {
    const el = this.canvas().nativeElement;
    const rect = el.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) * el.width) / rect.width,
      y: ((event.clientY - rect.top) * el.height) / rect.height,
    };
  }
}
