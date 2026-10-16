import { Component, inject, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Auth } from '@core/auth/auth';
import { Alert } from '@shared/ui/alert/alert';
import { Simulations } from '@core/api/simulations';
import { SimulationHistoryItem } from '@models/simulation/simulation-history.model';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, DecimalPipe, DatePipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  private router = inject(Router);
  private auth = inject(Auth);
  private alert = inject(Alert);
  private simulations = inject(Simulations);

  history: SimulationHistoryItem[] = [];
  loading = true;

  ngOnInit(): void {
    this.simulations.getHistory().subscribe({
      next: (response) => { this.history = response; this.loading = false; },
      error: (error) => { this.alert.showApiError(error); this.loading = false; }
    });
  }

  get latest(): SimulationHistoryItem | null {
    return this.history[0] ?? null;
  }

  get recent(): SimulationHistoryItem[] {
    return this.history.slice(1, 6);
  }

  get strategiesTried(): number {
    return new Set(this.history.flatMap(h => h.strategies)).size;
  }

  get bestRun(): SimulationHistoryItem | null {
    const withReturn = this.history.filter(h => h.total_return_pct !== null);
    if (withReturn.length === 0) return null;
    return withReturn.reduce((best, h) => (h.total_return_pct! > best.total_return_pct! ? h : best));
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

  async onLogout() {
    const confirmed = await this.alert.confirm('Do you want to log out?');
    if (confirmed) {
      this.auth.logout();
      this.router.navigate(['/']);
    }
  }
}