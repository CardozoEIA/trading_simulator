import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReactiveFormsModule, FormGroup, FormControl, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Risk } from '@core/api/risk';
import { Alert } from '@shared/ui/alert/alert';
import { StepIndicator } from '@shared/ui/step-indicator/step-indicator';
import { RiskConfiguration } from '@models/simulation/risk-configuration.model';
import { RiskConfigurationResponse } from '@models/simulation/risk-configuration-response.model';
import { PENDING_RISK_CHANGE_KEY } from '@models/agent/chat.model';
import { HelpHint } from '@shared/ui/help-hint/help-hint';

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
  imports: [ReactiveFormsModule, StepIndicator, HelpHint],
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
  suggestedNotice: string | null = null;

  riskForm = new FormGroup({
    stopLossPercentage: new FormControl<number | null>(null, [Validators.required, percentageValidator]),
    maxPositionSize: new FormControl<number | null>(null, [Validators.required, percentageValidator]),
    maxDrawdown: new FormControl<number | null>(null, [Validators.required, percentageValidator]),
  });

  ngOnInit(): void {
    this.configurationId = this.route.snapshot.paramMap.get('configurationId');
    this.applyPendingRiskChange();
  }

  /** A risk value the student confirmed in the chat (guided mode). The student still reviews and saves it. */
  private applyPendingRiskChange(): void {
    const controls = {
      stop_loss_percentage: 'stopLossPercentage',
      max_position_size: 'maxPositionSize',
      max_drawdown: 'maxDrawdown',
    } as const;

    try {
      const raw = sessionStorage.getItem(PENDING_RISK_CHANGE_KEY);
      if (!raw) return;
      sessionStorage.removeItem(PENDING_RISK_CHANGE_KEY);

      const pending = JSON.parse(raw) as { parameter: keyof typeof controls; label: string; value: number; createdAt: number };
      const thirtyMinutes = 30 * 60 * 1000;
      if (Date.now() - pending.createdAt > thirtyMinutes) return;

      const control = controls[pending.parameter];
      if (!control || typeof pending.value !== 'number') return;

      this.riskForm.controls[control].setValue(pending.value);
      this.suggestedNotice = `Suggested by the assistant: ${pending.label} at ${pending.value}%. Review it and fill in the other limits.`;
    } catch {
      // Storage unavailable or malformed value: nothing to prefill.
    }
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
        this.router.navigate(['/confirm-config', this.configurationId]);
      },
      error: (error) => { this.alert.showApiError(error); }
    });
  }
  async onDashboardClick() {
    const confirmed = await this.alert.confirmLeaveWizard();
    if (confirmed) {
      this.router.navigate(['/dashboard']);
    }
  }
}