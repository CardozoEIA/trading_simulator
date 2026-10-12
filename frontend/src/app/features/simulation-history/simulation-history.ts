import { Component, inject, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Simulations } from '../../core/simulations';
import { Alert } from '../../shared/alert';
import { SimulationHistoryItem } from '../../models/simulation-history.model';

@Component({
  selector: 'app-simulation-history',
  imports: [RouterLink, DecimalPipe, DatePipe],
  templateUrl: './simulation-history.html',
  styleUrl: './simulation-history.css',
})
export class SimulationHistory implements OnInit {
  private simulations = inject(Simulations);
  private alert = inject(Alert);
  private router = inject(Router);

  history: SimulationHistoryItem[] = [];
  loading = true;

  ngOnInit(): void {
    this.simulations.getHistory().subscribe({
      next: (response) => { this.history = response; this.loading = false; },
      error: (error) => { this.alert.showApiError(error); this.loading = false; }
    });
  }

  open(item: SimulationHistoryItem): void {
    if (item.status === 'RUNNING') {
      this.router.navigate(['/simulation-status', item.id]);
    } else {
      this.router.navigate(['/simulation-decisions', item.id]);
    }
  }

  statusLabel(status: string): string {
    if (status === 'FINISHED') return 'Completed';
    if (status === 'STOPPED_BY_RISK') return 'Stopped by risk';
    return 'Running';
  }
}