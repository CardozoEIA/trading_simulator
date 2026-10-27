import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { DashboardLink } from '@shared/ui/dashboard-link/dashboard-link';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, DashboardLink],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected title = 'frontend';
}
