import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, inject, input, output, signal, viewChild } from '@angular/core';
import { Subscription } from 'rxjs';

import { Simulations } from '@core/api/simulations';
import { SimulationReport as Report } from '@models/agent/report.model';

const PRINT_STYLES = `
  body { font-family: Inter, Arial, sans-serif; color: #0B1B2B; margin: 2rem; }
  h1, h4 { font-family: Fraunces, Georgia, serif; }
  h1 { font-size: 1.6rem; margin: 0; }
  .meta { color: #5B7B8C; font-size: 0.8rem; margin: 0.3rem 0 1.5rem; }
  .report-section { break-inside: avoid; border-top: 1px solid #ddd; padding-top: 1rem; margin-top: 1rem; }
  h4 { font-size: 1.1rem; margin: 0 0 0.5rem; }
  .narrative { font-size: 0.9rem; line-height: 1.55; }
  .narrative.missing, .disclaimer .narrative { font-style: italic; color: #5B7B8C; font-size: 0.8rem; }
  dl { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem 1.5rem; margin: 0; }
  .report-row { display: flex; justify-content: space-between; border-bottom: 1px dashed #ccc; font-size: 0.82rem; padding: 0.25rem 0; }
  dt { color: #5B7B8C; } dd { margin: 0; font-weight: 600; }
  table { border-collapse: collapse; width: 100%; font-size: 0.78rem; margin-top: 0.75rem; }
  th, td { text-align: left; padding: 0.3rem 0.5rem; border-bottom: 1px solid #ddd; }
  th { color: #5B7B8C; }
  .note, .empty-text { color: #5B7B8C; font-size: 0.75rem; }
`;

@Component({
  selector: 'app-simulation-report',
  templateUrl: './simulation-report.html',
  styleUrl: './simulation-report.css',
  host: { '(document:keydown.escape)': 'close()' },
})
export class SimulationReport implements OnInit, AfterViewInit, OnDestroy {
  simulationId = input.required<string>();
  closed = output<void>();

  private simulations = inject(Simulations);
  private closeButton = viewChild<ElementRef<HTMLButtonElement>>('closeButton');
  private reportBody = viewChild<ElementRef<HTMLElement>>('reportBody');
  private subscription: Subscription | null = null;
  private copiedTimer: ReturnType<typeof setTimeout> | null = null;

  report = signal<Report | null>(null);
  loading = signal(true);
  error = signal('');
  copyState = signal<'idle' | 'copied' | 'failed'>('idle');

  ngOnInit(): void {
    this.load();
  }

  ngAfterViewInit(): void {
    this.closeButton()?.nativeElement.focus();
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
    if (this.copiedTimer) clearTimeout(this.copiedTimer);
  }

  load(): void {
    this.subscription?.unsubscribe();
    this.loading.set(true);
    this.error.set('');
    this.subscription = this.simulations.getReport(this.simulationId()).subscribe({
      next: (report) => {
        this.report.set(report);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.detail || 'Could not generate the report. Please try again.');
        this.loading.set(false);
      },
    });
  }

  close(): void {
    this.closed.emit();
  }

  async copy(): Promise<void> {
    const report = this.report();
    if (!report) return;
    try {
      await navigator.clipboard.writeText(report.markdown);
      this.copyState.set('copied');
    } catch {
      this.copyState.set('failed');
    }
    if (this.copiedTimer) clearTimeout(this.copiedTimer);
    this.copiedTimer = setTimeout(() => this.copyState.set('idle'), 2500);
  }

  download(): void {
    const report = this.report();
    if (!report) return;
    const blob = new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `simulation-report-${report.simulation_id.slice(0, 8)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  /** Prints only the report (browser print → save as PDF) from a hidden frame, not the page behind it. */
  print(): void {
    const report = this.report();
    const body = this.reportBody()?.nativeElement;
    if (!report || !body) return;

    const frame = document.createElement('iframe');
    frame.setAttribute('aria-hidden', 'true');
    frame.style.cssText = 'position:fixed;width:0;height:0;border:0;right:0;bottom:0;';
    document.body.appendChild(frame);

    const doc = frame.contentDocument!;
    doc.open();
    doc.write(`<!doctype html><html><head><meta charset="utf-8"><title></title><style>${PRINT_STYLES}</style></head><body></body></html>`);
    doc.close();
    doc.title = report.title;
    const heading = doc.createElement('h1');
    heading.textContent = report.title;
    const meta = doc.createElement('p');
    meta.className = 'meta';
    meta.textContent = `Generated on ${report.generated_at}`;
    doc.body.append(heading, meta, doc.importNode(body, true));

    frame.contentWindow!.addEventListener('afterprint', () => frame.remove());
    frame.contentWindow!.focus();
    frame.contentWindow!.print();
  }
}
