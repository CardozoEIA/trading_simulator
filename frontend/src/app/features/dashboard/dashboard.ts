import { Component, inject } from '@angular/core';
import { Backtest } from '../../core/backtest';
import { Router, RouterLink } from '@angular/router';
import { Auth } from '../../core/auth';
import { Alert } from '../../shared/alert';

@Component({
  selector: 'app-dashboard',
  imports: [ RouterLink ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard {

  private router = inject(Router)
  private auth = inject(Auth)
  private alert = inject(Alert)

  async onLogout(){
    const confirmed = await this.alert.confirm('Do you want to log out?');
    if (confirmed) {
      this.auth.logout()
      this.router.navigate(["/"])
      this.alert.showSuccess("You have logged out successfully!")
    }
  }

}
