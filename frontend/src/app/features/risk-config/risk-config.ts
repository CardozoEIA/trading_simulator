import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormGroup, FormControl, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Risk } from '../../core/risk';
import { Alert } from '../../shared/alert';
import { StepIndicator } from '../../shared/step-indicator/step-indicator';
import { RiskConfiguration } from '../../models/risk-configuration.model';
import { RiskConfigurationResponse } from '../../models/risk-configuration-response.model';

function percentageValidator(control: AbstractControl): ValidationErrors | null {
  const value = control.value;
  if (value === null || value === '') return null;
  if (value <= 0 || value > 100) {
    return { percentageOutOfRange: true };
  }
  return null;
}

@Component({
  selector: 'app-risk-config',
  imports: [ReactiveFormsModule, RouterLink, StepIndicator],
  templateUrl: './risk-config.html',
  styleUrl: './risk-config.css',
})
export class RiskConfig implements OnInit {

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private risk = inject(Risk);
  private alert = inject(Alert);

  configurationId: string | null = null;
  submitted = false;
  savedRisk: RiskConfigurationResponse | null = null;

  riskForm = new FormGroup({
    stopLossPercentage: new FormControl<number | null>(null, [Validators.required, percentageValidator]),
    maxPositionSize: new FormControl<number | null>(null, [Validators.required, percentageValidator]),
    maxDrawdown: new FormControl<number | null>(null, [Validators.required, percentageValidator]),
  });

  ngOnInit(): void {
    this.configurationId = this.route.snapshot.paramMap.get('configurationId');
  }

  onSubmit() {
    this.submitted = true;

    if (this.riskForm.invalid || !this.configurationId) {
      return;
    }

    const payload: RiskConfiguration = {
      configuration_id: this.configurationId,
      stop_loss_percentage: this.riskForm.value.stopLossPercentage ?? 0,
      max_position_size: this.riskForm.value.maxPositionSize ?? 0,
      max_drawdown: this.riskForm.value.maxDrawdown ?? 0,
    };

    this.risk.configureRisk(payload).subscribe({
      next: (response) => {
        this.savedRisk = response;
        this.alert.showSuccess('Risk configuration saved successfully!');
        this.router.navigate(['/confirm-config', this.configurationId]);
      },
      error: (error) => { this.alert.showApiError(error); }
    });
  }
}