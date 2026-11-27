import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  ListStockCounts$Params,
  PageStockCountOut,
  StockCountClose,
  StockCountCreate,
  StockCountEntry,
  StockCountLineOut,
  StockCountOut,
  cancelStockCount,
  closeStockCount,
  createStockCount,
  getStockCount,
  listStockCounts,
  postStockCount,
  recordStockCountLine,
  reopenStockCount,
} from '@trishul/core-api';

export type {
  StockCountCreate,
  StockCountEntry,
  StockCountLineOut,
  StockCountOut,
} from '@trishul/core-api';

export type StockCountQuery = ListStockCounts$Params;

/** Physical stock counts (backend /inv/stock-counts). */
@Injectable({ providedIn: 'root' })
export class StockCountApi {
  private readonly api = inject(ApiClient);

  list(query: StockCountQuery): Observable<PageStockCountOut> {
    return this.api.call(listStockCounts, query);
  }

  get(countId: number): Observable<StockCountOut> {
    return this.api.call(getStockCount, { countId });
  }

  create(body: StockCountCreate): Observable<StockCountOut> {
    return this.api.call(createStockCount, { body });
  }

  record(
    countId: number,
    body: StockCountEntry,
  ): Observable<StockCountLineOut> {
    return this.api.call(recordStockCountLine, { countId, body });
  }

  close(countId: number, body: StockCountClose): Observable<StockCountOut> {
    return this.api.call(closeStockCount, { countId, body });
  }

  reopen(countId: number): Observable<StockCountOut> {
    return this.api.call(reopenStockCount, { countId });
  }

  cancel(countId: number): Observable<StockCountOut> {
    return this.api.call(cancelStockCount, { countId });
  }

  post(countId: number): Observable<StockCountOut> {
    return this.api.call(postStockCount, { countId });
  }
}
