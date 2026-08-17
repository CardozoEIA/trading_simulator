import { Component, inject } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { Auth } from '../../../core/auth';
import { Router, RouterLink } from '@angular/router';

@Component({
  selector: 'app-register',
  imports: [ ReactiveFormsModule, RouterLink ],
  templateUrl: './register.html',
  styleUrl: './register.css',
})
export class Register {

  private auth = inject(Auth);
  private router = inject(Router);

  registerForm = new FormGroup({
    name: new FormControl('', [Validators.required]),
    email: new FormControl('', [Validators.required, Validators.email]),
    password: new FormControl('', [Validators.required])
  })

  onSubmit(){
    this.auth.register(this.registerForm.value.name ?? '',
      this.registerForm.value.email ?? '', this.registerForm.value.password ?? '').subscribe({
        next: (response) => { this.router.navigate(['/']) },
        error: (error) => { console.log(error) }
      })
  }
}
