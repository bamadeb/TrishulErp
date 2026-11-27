import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  BinMoveCreate,
  BinMoveOut,
  ItemStorageOut,
  ItemStorageUpdate,
  ListBinMoves$Params,
  PageBinMoveOut,
  PutAwayRow,
  createBinMove,
  getBinMove,
  getItemStorage,
  listBinMoves,
  listPutaway,
  updateItemStorage,
  withRowVersion,
} from '@trishul/core-api';

export type {
  BinMoveLineIn,
  BinMoveOut,
  ItemStorageOut,
  PutAwayRow,
  StorageRuleIn,
  StorageRuleOut,
} from '@trishul/core-api';

export type BinMoveQuery = ListBinMoves$Params;

/** Put-away and bin moves, and an item's storage type and home bins (backend /inv/putaway, /inv/bin-moves). */
@Injectable({ providedIn: 'root' })
export class BinMoveApi {
  private readonly api = inject(ApiClient);

  putaway(locationId: number): Observable<PutAwayRow[]> {
    return this.api.call(listPutaway, { locationId });
  }

  move(body: BinMoveCreate): Observable<BinMoveOut> {
    return this.api.call(createBinMove, { body });
  }

  history(query: BinMoveQuery): Observable<PageBinMoveOut> {
    return this.api.call(listBinMoves, query);
  }

  get(moveId: number): Observable<BinMoveOut> {
    return this.api.call(getBinMove, { moveId });
  }

  storage(itemId: number): Observable<ItemStorageOut> {
    return this.api.call(getItemStorage, { itemId });
  }

  setStorage(
    current: ItemStorageOut,
    body: ItemStorageUpdate,
  ): Observable<ItemStorageOut> {
    return this.api.call(
      updateItemStorage,
      { itemId: current.itemId, body },
      withRowVersion(current.rowVersion),
    );
  }
}
