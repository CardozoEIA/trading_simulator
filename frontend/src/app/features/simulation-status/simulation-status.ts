import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Simulations } from '../../core/simulations';
import { Alert } from '../../shared/alert';
import { SimulationResponse } from '../../models/simulation-response.model';

@Component({
  selector: 'app-simulation-status',
  imports: [RouterLink],
  templateUrl: './simulation-status.html',
  styleUrl: './simulation-status.css',
})
export class SimulationStatus implements OnInit, OnDestroy {

  private route = inject(ActivatedRoute);
  private simulations = inject(Simulations);
  private alert = inject(Alert);

  simulationId: string | null = null;
  simulation: SimulationResponse | null = null;
  private pollHandle: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.simulationId = this.route.snapshot.paramMap.get('simulationId');

    if (!this.simulationId) {
      return;
    }

    this.fetchStatus();
    this.pollHandle = setInterval(() => this.fetchStatus(), 3000);
  }

  ngOnDestroy(): void {
    if (this.pollHandle) {
      clearInterval(this.pollHandle);
    }
  }

  private fetchStatus() {
    if (!this.simulationId) return;

    this.simulations.getSimulationStatus(this.simulationId).subscribe({
      next: (response) => {
        this.simulation = response;
        if (response.status !== 'RUNNING' && this.pollHandle) {
          clearInterval(this.pollHandle);
        }
      },
      error: (error) => {
        this.alert.showApiError(error);
        if (this.pollHandle) clearInterval(this.pollHandle);
      }
    });
  }
}