import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { Simulations } from '../../core/simulations';
import { Alert } from '../../shared/alert';
import { Decision } from '../../models/decision.model';
import { Trade } from '../../models/trade.model';
import { EquityPoint } from '../../models/equity-point.model';
import { Signal } from '../../models/signal.model';
import { ConfigurationSummaryResponse } from '../../models/configuration-summary-response.model';

interface RoundTrip {
  entryDate: string;
  exitDate: string;
  entryPrice: number;
  exitPrice: number;
  profitPct: number;
}

@Component({
  selector: 'app-simulation-decisions',
  imports: [RouterLink, DecimalPipe],
  templateUrl: './simulation-decisions.html',
  styleUrl: './simulation-decisions.css',
})
export class SimulationDecisions implements OnInit {
  private route = inject(ActivatedRoute);
  private simulations = inject(Simulations);
  private alert = inject(Alert);

  simulationId: string | null = null;
  summary: ConfigurationSummaryResponse | null = null;
  decisions: Decision[] = [];
  trades: Trade[] = [];
  equityCurve: EquityPoint[] = [];
  signals: Signal[] = [];
  loading = true;
  showAllDecisions = false;

  ngOnInit(): void {
    this.simulationId = this.route.snapshot.paramMap.get('simulationId');
    if (!this.simulationId) return;

    this.simulations.getSimulationStatus(this.simulationId).subscribe({
      next: (status) => {
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

  get roundTrips(): RoundTrip[] {
    const pairs: RoundTrip[] = [];
    for (let i = 0; i + 1 < this.trades.length; i += 2) {
      const entry = this.trades[i];
      const exit = this.trades[i + 1];
      if (entry.type === 'BUY' && exit.type === 'SELL') {
        pairs.push({
          entryDate: entry.date,
          exitDate: exit.date,
          entryPrice: entry.price,
          exitPrice: exit.price,
          profitPct: ((exit.price / entry.price) - 1) * 100
        });
      }
    }
    return pairs;
  }

  get winCount(): number {
    return this.roundTrips.filter(r => r.profitPct > 0).length;
  }

  get winRate(): number {
    if (this.roundTrips.length === 0) return 0;
    return (this.winCount / this.roundTrips.length) * 100;
  }

  get unexecutedSignals(): number {
    return this.signalDecisions.length - this.trades.length;
  }

  get chartWidth(): number {
    return Math.max(this.equityCurve.length * 4, 100);
  }

  get chartPoints(): string {
    if (this.equityCurve.length === 0) return '';
    const values = this.equityCurve.map(e => e.portfolio_value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return values
      .map((v, i) => `${i * 4},${100 - ((v - min) / range) * 100}`)
      .join(' ');
  }
  

  getSignalForDate(date: string): Signal | undefined {
    return this.signals.find(s => s.date === date);
  }
  getUnexecutedReason(d: Decision): string {
    if (d.rejection_reason) return d.rejection_reason;
    if (d.executed) return '';
    return d.action === 'BUY' ? 'Already fully invested — no cash available' : 'No open position to sell';
  }
}