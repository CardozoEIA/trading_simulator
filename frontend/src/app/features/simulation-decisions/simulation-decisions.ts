import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { Simulations } from '../../core/simulations';
import { Alert } from '../../shared/alert';
import { Decision } from '../../models/decision.model';
import { Trade } from '../../models/trade.model';
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
  }

  get signalDecisions(): Decision[] {
    return this.decisions.filter(d => d.action !== 'HOLD');
  }

  get finalValue(): number {
    if (this.trades.length === 0) return this.summary?.initial_capital ?? 0;
    return this.trades[this.trades.length - 1].portfolio_value_after;
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
}