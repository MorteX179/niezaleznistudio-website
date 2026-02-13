fetch('list.json').then(r=>r.json()).then(list=>
{
  var me = window.location.pathname.split('/').pop();
  var item = list.find(function(i){return i.name===me});
  if(!item) return;
  var titleEl = document.getElementById('title');
  if(titleEl) titleEl.textContent = item.title || item.name;
  var descEl = document.getElementById('desc');
  if(descEl) descEl.textContent = item.desc || '';
  var c = document.getElementById('cast');
  if(Array.isArray(item.cast) && item.cast.length)
  {
    var castHTML = '<strong>Obsada:</strong><br>';
    item.cast.forEach(function(member)
    {
      if(typeof member === 'string')
      {
        castHTML += member + '<br>';
      }
      else if(typeof member === 'object' && member.name)
      {
        var line = '';
        if(member.icon)
        {
          line = '<img src="' + member.icon + '" style="width:25px;height:25px;vertical-align:middle;margin-right:6px;border-radius:3px;" alt="' + member.name + '"/>';
        }
        line += member.name;
        castHTML += line + '<br>';
      }
    });
    c.innerHTML = castHTML;
  }
  else if(c)
  {
    c.style.display='none';
  }
  var t = document.getElementById('team');
  if(Array.isArray(item.team) && item.team.length)
  {
    var teamHTML = '<strong>Ekipa Projektu:</strong><br>';
    item.team.forEach(function(member)
    {
      if(typeof member === 'string')
      {
        teamHTML += member + '<br>';
      }
      else if(typeof member === 'object' && member.name)
      {
        var line = '';
        if(member.icon)
        {
          line = '<img src="' + member.icon + '" style="width:25px;height:22px;vertical-align:middle;margin-right:6px;border-radius:3px;" alt="' + member.name + '"/>';
        }
        line += member.name;
        teamHTML += line + '<br>';
      }
    });
    t.innerHTML = teamHTML;
  }
  else if(t)
  {
    t.style.display='none';
  }
  var e = document.getElementById('extra');
  if(item.details && e)
  {
    e.innerHTML = '<strong>Szczegóły:</strong><br>' + item.details;
  }
  else if(e)
  {
    e.style.display='none';
  }
  var main = document.querySelector('main.container');
  if(main)
  {
    var split = document.createElement('div');
    split.className = 'splitDiv';
    var left = document.createElement('div');
    left.className = 'leftBox';

    var ids = ['title','desc','cast','team','extra'];
    ids.forEach(function(id)
    {
      var el = document.getElementById(id);
      if(el) left.appendChild(el);
    });

    var back = document.createElement('p');
    back.style.marginTop = '1rem';
    var backA = document.createElement('a');
    backA.href = '../index.html';
    backA.className = 'button';
    backA.textContent = 'Powrót';
    back.appendChild(backA);
    left.appendChild(back);

    split.appendChild(left);

    var right = document.createElement('div');
    right.className = 'rightPic';

    if(item.image)
    {
      var link = document.createElement('a');
      link.href = item.videoUrl || 'https://www.youtube.com/watch?v=33pJt8sqMw4';
      link.target = '_blank';

      var img = document.createElement('img');
      img.src = item.image;
      img.alt = item.title || '';

      link.appendChild(img);
      right.appendChild(link);
    }


split.appendChild(right);

    main.innerHTML = '';
    main.appendChild(split);
  }
}).catch(()=>{});
