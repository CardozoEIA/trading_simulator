import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { Subscription } from 'rxjs';

import { Simulations } from '@core/api/simulations';
import { CompareSide, SimulationComparison } from '@models/agent/compare.model';

@Component({
  selector: 'app-simulation-compare',
  imports: [RouterLink, DatePipe],
  templateUrl: './simulation-compare.html',
  styleUrl: './simulation-compare.css',
})
export class SimulationCompare implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private simulations = inject(Simulations);
  private subscription: Subscription | null = null;

  simulationA: string | null = null;
  simulationB: string | null = null;

  comparison = signal<SimulationComparison | null>(null);
  loading = signal(false);
  error = signal('');

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    this.simulationA = params.get('a');
    this.simulationB = params.get('b');
    if (!this.simulationA || !this.simulationB) {
      this.error.set('Select two simulations in your history to compare them.');
      return;
    }
    this.load();
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  load(): void {
    if (!this.simulationA || !this.simulationB) return;
    this.subscription?.unsubscribe();
    this.loading.set(true);
    this.error.set('');
    this.subscription = this.simulations.compareSimulations(this.simulationA, this.simulationB).subscribe({
      next: (comparison) => {
        this.comparison.set(comparison);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.detail || 'Could not compare the simulations. Please try again.');
        this.loading.set(false);
      },
    });
  }

  verdict(winner: CompareSide): string {
    if (winner === 'tie') return 'Both simulations had the same total return';
    return `Simulation ${winner.toUpperCase()} performed better by total return`;
  }

  get changedCount(): number {
    return this.comparison()?.configuration_diff.filter(c => c.changed).length ?? 0;
  }
}
