const PEOPLE = [
  {name: 'Alice Monroe', role: 'Product Designer', location: 'New York, NY'},
  {name: 'Bob Chen', role: 'Software Engineer', location: 'San Francisco, CA'},
  {name: 'Carlos Ruiz', role: 'Data Scientist', location: 'Austin, TX'},
  {name: 'Denise Patel', role: 'Marketing Lead', location: 'Seattle, WA'},
  {name: 'Ethan Li', role: 'CTO', location: 'Boston, MA'},
  {name: 'Fiona Gomez', role: 'UX Researcher', location: 'Denver, CO'},
  {name: 'Grace Park', role: 'Designer', location: 'Brooklyn, NY'},
  {name: 'Hassan Ali', role: 'Frontend Engineer', location: 'Chicago, IL'}
];

const q = (sel) => document.querySelector(sel);
const resultsNode = q('#results');
const suggestionsNode = q('#suggestions');
const input = q('#search');
const btn = q('#searchBtn');

function initials(name){
  return name.split(' ').slice(0,2).map(n=>n[0]).join('').toUpperCase();
}

function renderCard(person){
  const el = document.createElement('article');
  el.className = 'card';
  el.innerHTML = `
    <div class="avatar">${initials(person.name)}</div>
    <div class="info">
      <p class="name">${person.name}</p>
      <p class="role">${person.role} • ${person.location}</p>
    </div>
  `;
  return el;
}

function showResults(list){
  resultsNode.innerHTML = '';
  if(!list.length){
    resultsNode.innerHTML = '<p class="hint">No results. Try a different query or check spelling.</p>';
    return;
  }
  list.forEach(p => resultsNode.appendChild(renderCard(p)));
}

function buildSuggestions(list){
  suggestionsNode.innerHTML = '';
  if(!list.length){
    suggestionsNode.hidden = true;
    return;
  }
  suggestionsNode.hidden = false;
  list.slice(0,6).forEach(p => {
    const li = document.createElement('li');
    li.textContent = `${p.name} — ${p.role}`;
    li.addEventListener('click', ()=>{
      input.value = p.name;
      suggestionsNode.hidden = true;
      showResults([p]);
    });
    suggestionsNode.appendChild(li);
  });
}

function search(query){
  const q = String(query||'').trim().toLowerCase();
  if(!q) return [];
  return PEOPLE.filter(p => {
    return p.name.toLowerCase().includes(q) || p.role.toLowerCase().includes(q) || p.location.toLowerCase().includes(q);
  });
}

input.addEventListener('input', (e)=>{
  const val = e.target.value;
  if(!val) {
    suggestionsNode.hidden = true;
    return;
  }
  const found = search(val);
  buildSuggestions(found);
});

input.addEventListener('keydown', (e)=>{
  if(e.key === 'Enter'){
    const val = input.value;
    showResults(search(val));
    suggestionsNode.hidden = true;
  }
});

btn.addEventListener('click', ()=>{
  showResults(search(input.value));
  suggestionsNode.hidden = true;
});

// initial sample
showResults(PEOPLE.slice(0,4));
