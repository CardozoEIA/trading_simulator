import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-step-indicator',
  imports: [],
  templateUrl: './step-indicator.html',
  styleUrl: './step-indicator.css',
})
export class StepIndicator {
  @Input() steps: string[] = [];
  @Input() currentStep: number = 1;
}