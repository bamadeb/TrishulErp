import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  BrandCreate,
  BrandFormOptions,
  BrandItem,
  BrandUpdate,
  CompanyChoice,
  BrandCompanyCreate,
  activateBrand,
  createBrand,
  createBrandCompany,
  deactivateBrand,
  getBrandFormOptions,
  listBrands,
  updateBrand,
  withRowVersion,
} from '@trishul/core-api';

/** /core/brands: the brands (and the company behind each) that the brand dropdowns offer. */
@Injectable({ providedIn: 'root' })
export class BrandApi {
  private readonly api = inject(ApiClient);

  list(): Observable<BrandItem[]> {
    return this.api.call(listBrands);
  }

  /** The companies a brand can belong to. */
  formOptions(): Observable<BrandFormOptions> {
    return this.api.call(getBrandFormOptions);
  }

  /** A new company, available in the brand form at once. */
  createCompany(body: BrandCompanyCreate): Observable<CompanyChoice> {
    return this.api.call(createBrandCompany, { body });
  }

  create(body: BrandCreate): Observable<BrandItem> {
    return this.api.call(createBrand, { body });
  }

  /** rowVersion comes with the brand; a newer change by someone else gives 409. */
  update(brand: BrandItem, body: BrandUpdate): Observable<BrandItem> {
    return this.api.call(
      updateBrand,
      { brandId: brand.id, body },
      withRowVersion(brand.rowVersion),
    );
  }

  setActive(brand: BrandItem, active: boolean): Observable<BrandItem> {
    return this.api.call(active ? activateBrand : deactivateBrand, {
      brandId: brand.id,
    });
  }
}
