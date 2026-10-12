import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { Simulations } from '../../core/simulations';
import { Alert } from '../../shared/alert';
import { Decision } from '../../models/decision.model';
import { Trade } from '../../models/trade.model';
import { EquityPoint } from '../../models/equity-point.model';
import { Signal } from '../../models/signal.model';
import { SimulationMetrics } from '../../models/metrics.model';
import { ConfigurationSummaryResponse } from '../../models/configuration-summary-response.model';
import { EquityChart } from '../../shared/equity-chart/equity-chart';
import { ChartHighlight } from '../../shared/equity-chart/equity-chart';
import { Highlight, HighlightKind, SimulationInsights } from '../../models/insights.model';

@Component({
  selector: 'app-simulation-decisions',
  imports: [RouterLink, DecimalPipe, EquityChart],
  templateUrl: './simulation-decisions.html',
  styleUrl: './simulation-decisions.css',
})
export class SimulationDecisions implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private simulations = inject(Simulations);
  private alert = inject(Alert);

  simulationId: string | null = null;
  summary: ConfigurationSummaryResponse | null = null;
  simulationStatus: string | null = null;
  stopReason: string | null = null;
  decisions: Decision[] = [];
  trades: Trade[] = [];
  equityCurve: EquityPoint[] = [];
  signals: Signal[] = [];
  metrics: SimulationMetrics | null = null;
  loading = true;
  showAllDecisions = false;

  ngOnInit(): void {
    this.simulationId = this.route.snapshot.paramMap.get('simulationId');
    if (!this.simulationId) return;

    this.simulations.getSimulationStatus(this.simulationId).subscribe({
      next: (status) => {
        this.simulationStatus = status.status;
        this.stopReason = status.stop_reason;
        this.simulations.getConfigurationSummary(status.configuration_id).subscribe({
          next: (summary) => { this.summary = summary; },
          error: (error) => { this.alert.showApiError(error); }
        });
      },
      error: (error) => { this.alert.showApiError(error); }
    });

    this.simulations.getDecisions(this.simulationId).subscribe({
      next: (response) => { this.decisions = response; this.loading = false; },
      error: (error) => { this.alert.showApiError(error); this.loading = false; }
    });

    this.simulations.getTrades(this.simulationId).subscribe({
      next: (response) => { this.trades = response; },
      error: (error) => { this.alert.showApiError(error); }
    });

    this.simulations.getEquityCurve(this.simulationId).subscribe({
      next: (response) => { this.equityCurve = response; },
      error: (error) => { this.alert.showApiError(error); }
    });

    this.simulations.getSignals(this.simulationId).subscribe({
      next: (response) => { this.signals = response; },
      error: (error) => { this.alert.showApiError(error); }
    });

    this.simulations.getMetrics(this.simulationId).subscribe({
      next: (response) => { this.metrics = response; },
      error: (error) => { this.alert.showApiError(error); }
    });
    this.loadInsights();
  }

  ngOnDestroy(): void {
    if (this.insightsTimer) clearTimeout(this.insightsTimer);
  }

  // --- Agent highlights (US-26) ---
  insights: SimulationInsights | null = null;
  selectedHighlight: Highlight | null = null;
  private insightsTimer: ReturnType<typeof setTimeout> | null = null;
  private insightsPolls = 0;

  private loadInsights(): void {
    if (!this.simulationId) return;
    this.simulations.getInsights(this.simulationId).subscribe({
      // Highlights are optional: errors here never affect the rest of the results view.
      next: (response) => {
        this.insights = response;
        if (this.selectedHighlight) {
          this.selectedHighlight = response.highlights.find(h => h.kind === this.selectedHighlight!.kind) ?? null;
        }
        if (response.status === 'PENDING' && this.insightsPolls < 60) {
          this.insightsPolls++;
          this.insightsTimer = setTimeout(() => this.loadInsights(), 3000);
        }
      },
      error: () => { this.insights = null; },
    });
  }

  highlight(kind: HighlightKind): Highlight | undefined {
    return this.insights?.highlights.find(h => h.kind === kind);
  }

  get headlineHighlights(): Highlight[] {
    return (this.insights?.highlights ?? []).filter(h => h.kind === 'BUY_AND_HOLD' || h.kind === 'RISK_STOP');
  }

  get chartHighlights(): Highlight[] {
    return (this.insights?.highlights ?? []).filter(h => h.kind !== 'BUY_AND_HOLD' && h.kind !== 'RISK_STOP');
  }

  get chartMarkers(): ChartHighlight[] {
    const dd = this.highlight('MAX_DRAWDOWN');
    if (!dd || dd.dates.length < 2) return [];
    return [
      { date: dd.dates[0], text: 'Peak' },
      { date: dd.dates[1], text: dd.label.replace('Largest drop ', 'Low ') },
    ];
  }

  /** Best/worst trade highlight for a row of the trades table (both the BUY and the SELL). */
  tradeHighlight(t: Trade): Highlight | undefined {
    return ['BEST_TRADE', 'WORST_TRADE']
      .map(k => this.highlight(k as HighlightKind))
      .find(h => !!h && ((t.type === 'BUY' && t.date === h.dates[0]) || (t.type === 'SELL' && t.date === h.dates[1])));
  }

  openHighlight(h: Highlight): void {
    this.selectedHighlight = h;
  }

  closeHighlight(): void {
    this.selectedHighlight = null;
  }

  retryInsights(): void {
    if (!this.simulationId) return;
    this.simulations.generateInsights(this.simulationId).subscribe({
      next: (response) => {
        this.insights = response;
        this.insightsPolls = 0;
        if (this.insightsTimer) clearTimeout(this.insightsTimer);
        this.insightsTimer = setTimeout(() => this.loadInsights(), 3000);
      },
      error: (error) => { this.alert.showApiError(error); },
    });
  }

  get signalDecisions(): Decision[] {
    return this.decisions.filter(d => d.action !== 'HOLD');
  }

  get finalValue(): number {
    if (this.equityCurve.length > 0) {
      return this.equityCurve[this.equityCurve.length - 1].portfolio_value;
    }
    if (this.trades.length > 0) {
      return this.trades[this.trades.length - 1].portfolio_value_after;
    }
    return this.summary?.initial_capital ?? 0;
  }

  get totalReturnPct(): number {
    if (!this.summary || this.summary.initial_capital === 0) return 0;
    return ((this.finalValue / this.summary.initial_capital) - 1) * 100;
  }

  get isOpenPosition(): boolean {
    return this.trades.length > 0 && this.trades[this.trades.length - 1].type === 'BUY';
  }

  get benchmarkDeltaPct(): number | null {
    if (!this.summary?.benchmark) return null;
    return this.totalReturnPct - this.summary.benchmark.total_return_pct;
  }

  get beatBenchmark(): boolean {
    return (this.benchmarkDeltaPct ?? 0) >= 0;
  }

  get unexecutedSignals(): number {
    return this.signalDecisions.length - this.trades.length;
  }





  getSignalForDate(date: string): Signal | undefined {
    return this.signals.find(s => s.date === date);
  }

  getUnexecutedReason(d: Decision): string {
    if (d.rejection_reason) return d.rejection_reason;
    if (d.executed) return '';
    return d.action === 'BUY' ? 'Already fully invested — no cash available' : 'No open position to sell';
  }

  // --- Agent explanation modal (US-20) ---
  explanationOpen = false;
  explanationDate: string | null = null;
  explanationText = '';
  explanationLoading = false;
  explanationError = '';

  openExplanation(date: string): void {
    if (!this.simulationId) return;
    this.explanationOpen = true;
    this.explanationDate = date;
    this.explanationText = '';
    this.explanationError = '';
    this.explanationLoading = true;

    this.simulations.explainDecision(this.simulationId, date).subscribe({
      next: (response) => {
        this.explanationText = response.explanation;
        this.explanationLoading = false;
      },
      error: (error) => {
        this.explanationError =
          error?.error?.detail ||
          'Could not generate the explanation. Please try again.';
        this.explanationLoading = false;
      }
    });
  }

  closeExplanation(): void {
    this.explanationOpen = false;
    this.explanationDate = null;
    this.explanationText = '';
    this.explanationError = '';
    this.explanationLoading = false;
  }
}