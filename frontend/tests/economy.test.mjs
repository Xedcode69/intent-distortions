import test from "node:test";
import assert from "node:assert/strict";
import {simulateEconomy,monthLabel} from "../lib/economy.ts";
test("five sales and two exits conserve all auction proceeds",()=>{
 const x=simulateEconomy(5,2,100n);assert.deepEqual(x,{gross:500n,treasury:100n,withdrawals:64n,pot:240n,rollover:96n,tickets:3});
});
test("rounding and every allowed exit count preserve funds",()=>{
 for(let sales=0;sales<=5;sales++)for(let exits=0;exits<=sales;exits++)for(const price of [0n,1n,101n,104n,10n**30n]){
  const x=simulateEconomy(sales,exits,price);assert.equal(x.treasury+x.withdrawals+x.pot+x.rollover,x.gross);
 }
 assert.equal(monthLabel(202612),"December 2026");assert.throws(()=>simulateEconomy(5,6,100n));
});
