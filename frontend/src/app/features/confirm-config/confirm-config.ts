import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Simulations } from '../../core/simulations';
import { Alert } from '../../shared/alert';
import { StepIndicator } from '../../shared/step-indicator/step-indicator';
import { ConfigurationSummaryResponse } from '../../models/configuration-summary-response.model';

@Component({
  selector: 'app-confirm-config',
  imports: [RouterLink, StepIndicator],
  templateUrl: './confirm-config.html',
  styleUrl: './confirm-config.css',
})
export class ConfirmConfig implements OnInit {

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private simulations = inject(Simulations);
  private alert = inject(Alert);

  configurationId: string | null = null;
  summary: ConfigurationSummaryResponse | null = null;
  starting = false;

  ngOnInit(): void {
    this.configurationId = this.route.snapshot.paramMap.get('configurationId');

    if (!this.configurationId) {
      return;
    }

    this.simulations.getConfigurationSummary(this.configurationId).subscribe({
      next: (response) => { this.summary = response; },
      error: (error) => { this.alert.showApiError(error); }
    });
  }

  onConfirm() {
    if (!this.configurationId || this.starting) {
      return;
    }

    this.starting = true;

    this.simulations.startSimulation(this.configurationId).subscribe({
      next: (response) => {
        this.router.navigate(['/simulation-status', response.id]);
      },
      error: (error) => {
        this.starting = false;
        this.alert.showApiError(error);
      }
    });
  }
}