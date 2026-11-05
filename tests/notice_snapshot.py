"""Exclude the intentional notice addition when comparing pre-existing department UI."""
def content_text(locator):
    return locator.evaluate("""e=>{
      const cards=[...e.querySelectorAll('.nc-card')], previous=cards.map(c=>c.getAttribute('style'));
      try { cards.forEach(c=>c.style.setProperty('display','none','important')); return e.innerText; }
      finally { cards.forEach((c,i)=>previous[i]===null?c.removeAttribute('style'):c.setAttribute('style',previous[i])); }
    }""")
