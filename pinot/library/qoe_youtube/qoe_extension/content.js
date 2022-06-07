/*jshint esversion: 9 */

let s = document.createElement('script');
s.src = chrome.runtime.getURL('script.js');
s.onload = function() {
    "use strict";
    this.remove();
};
(document.head || document.documentElement).appendChild(s);