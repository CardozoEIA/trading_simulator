import { Component, inject, Input, OnChanges, OnDestroy } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Simulations } from '../../core/simulations';
import { SimulationInsights } from '../../models/insights.model';

const POLL_MS = 3000;
const MAX_POLLS = 60; // ~3 minutes; the local model can be slow

@Component({
  selector: 'app-simulation-insights',
  templateUrl: './simulation-insights.html',
  styleUrl: './simulation-insights.css',
})
export class SimulationInsightsPanel implements OnChanges, OnDestroy {
  private simulations = inject(Simulations);

  @Input() simulationId: string | null = null;

  data: SimulationInsights | null = null;
  loading = true;
  requestError: string | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private polls = 0;

  ngOnChanges(): void {
    this.stopPolling();
    if (!this.simulationId) return;
    this.loading = true;
    this.polls = 0;
    this.fetch();
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  get status() {
    return this.data?.status ?? 'NOT_GENERATED';
  }

  generate(): void {
    if (!this.simulationId) return;
    this.requestError = null;
    this.simulations.generateInsights(this.simulationId).subscribe({
      next: (response) => {
        this.data = { ...response, insights: [], error: null, generated_at: null };
        this.polls = 0;
        this.schedule();
      },
      error: (error: HttpErrorResponse) => {
        this.requestError = error?.error?.detail ?? 'Could not start generating insights. Please try again.';
      },
    });
  }

  private fetch(): void {
    if (!this.simulationId) return;
    this.simulations.getInsights(this.simulationId).subscribe({
      next: (response) => {
        this.data = response;
        this.loading = false;
        if (response.status === 'PENDING') this.schedule();
      },
      error: () => {
        // Insights are optional: a failure here never affects the rest of the results view.
        this.loading = false;
        this.requestError = 'Insights could not be loaded right now.';
      },
    });
  }

  private schedule(): void {
    this.stopPolling();
    if (this.polls >= MAX_POLLS) return;
    this.polls++;
    this.timer = setTimeout(() => this.fetch(), POLL_MS);
  }

  private stopPolling(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }
}
