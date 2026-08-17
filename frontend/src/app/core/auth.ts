import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { LoginResponse } from '../models/login-response.model';
import { RegisterResponse } from '../models/register-response.model';
import { environment } from '../../environments/environment';
@Injectable({
  providedIn: 'root',
})
export class Auth {

  private http = inject(HttpClient)
  private baseUrl = environment.apiUrl;

  public login(email: string, password: string){
    return this.http.post<LoginResponse>(`${this.baseUrl}/auth/login`, { email, password });
  }

  public register(name: string, email: string, password: string) {
    return this.http.post<RegisterResponse>(`${this.baseUrl}/users/`, { name, email, password })
  }


  // Guardar token usando localStorage

  public saveToken(token: string){
    localStorage.setItem('access_token', token)
  }

  public getToken(){
    return localStorage.getItem('access_token')
  }

  public logout(){
    localStorage.removeItem('access_token')
  }
}
