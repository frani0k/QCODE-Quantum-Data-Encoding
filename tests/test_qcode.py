import json
import numpy as np
import pytest
from qiskit.quantum_info import Statevector, Operator
from src.encoding import encoding_circuit, scale_features
from src.dataset import make_dataset, labels
from src.variational_classifier import circuit, encoded_states, probabilities, predict
from src.training import loss_gradient, train
from src.evaluation import summarize, save_json, load_json, resources


def test_ry_analytic():
    x=np.array([0.4,1.2])
    expected=np.kron([np.cos(x[1]/2),np.sin(x[1]/2)],[np.cos(x[0]/2),np.sin(x[0]/2)])
    np.testing.assert_allclose(Statevector.from_instruction(encoding_circuit(x,'RY')).data,expected,atol=1e-14)


def test_zz_analytic_and_interaction():
    x=np.array([0.3,0.7]); z0=np.array([1,-1,1,-1]); z1=np.array([1,1,-1,-1])
    phi=(np.pi-x[0])*(np.pi-x[1])
    expected=np.exp(1j*(x[0]*z0+x[1]*z1+phi*z0*z1))/2
    np.testing.assert_allclose(Statevector.from_instruction(encoding_circuit(x,'ZZ')).data,expected,atol=1e-14)
    assert not np.allclose(expected,Statevector.from_instruction(encoding_circuit(x+[0.1,0],'ZZ')).data)


@pytest.mark.parametrize('variant',['RY','ZZ'])
def test_normalization(variant):
    states=encoded_states(np.array([[0.,0.],[np.pi,np.pi],[0.3,1.7]]),variant)
    np.testing.assert_allclose(np.sum(abs(states)**2,axis=1),1,atol=1e-14)


def test_labels_and_scaling():
    np.testing.assert_array_equal(labels(np.array([[-1,-1],[-1,1],[1,-1],[1,1],[0,-1]])),[0,1,1,0,0])
    np.testing.assert_allclose(scale_features(np.array([[-1,0],[1,-1]])),[[0,np.pi/2],[np.pi,0]])


def test_split_no_leakage_and_reproducible():
    a=make_dataset(4); b=make_dataset(4)
    for key in a: np.testing.assert_array_equal(a[key],b[key])
    assert len(a['train_idx'])==800 and len(a['test_idx'])==200
    assert not set(a['train_idx']) & set(a['test_idx'])
    np.testing.assert_allclose(a['X_train'],scale_features(a['raw'][a['train_idx']]))
    np.testing.assert_array_equal(a['y_test'],labels(a['raw'][a['test_idx']]))
    assert abs(a['y_train'].mean()-a['y_test'].mean())<0.01


@pytest.mark.parametrize('variant',['RY','ZZ'])
def test_vectorized_matches_qiskit(variant):
    x=np.random.default_rng(12).uniform(0,np.pi,(6,2)); theta=np.array([0.2,-0.7,1.1,0.8])
    expected=[Statevector.from_instruction(circuit(row,theta,variant)).probabilities([0])[1] for row in x]
    np.testing.assert_allclose(probabilities(encoded_states(x,variant),theta),expected,atol=1e-14)
    assert circuit(x[0],None,variant).num_parameters==4


def test_measurement_and_decision():
    x=np.array([[0,0],[np.pi,0]])
    np.testing.assert_allclose(probabilities(encoded_states(x,'RY'),np.zeros(4)),[0,1],atol=1e-14)
    np.testing.assert_array_equal(predict(np.array([0,0.5,1])),[0,1,1])


@pytest.mark.parametrize('variant',['RY','ZZ'])
def test_gradient_finite_difference(variant):
    states=encoded_states(np.array([[0.3,0.7],[1.2,2.3],[2.4,0.8]]),variant); y=np.array([0,1,1]); t=np.array([0.1,-0.2,0.3,0.4])
    loss,grad=loss_gradient(states,y,t)
    finite=[]
    for j in range(4):
        shift=np.zeros(4); shift[j]=1e-6
        finite.append((loss_gradient(states,y,t+shift)[0]-loss_gradient(states,y,t-shift)[0])/2e-6)
    np.testing.assert_allclose(grad,finite,atol=1e-7)


def test_training_reproducible_and_improves():
    x=np.random.default_rng(5).uniform(0,np.pi,(30,2)); y=(x[:,0]>1.5).astype(int); t=np.zeros(4)
    a=train(x,y,'RY',t,steps=5); b=train(x,y,'RY',t,steps=5)
    np.testing.assert_array_equal(a['theta'],b['theta']); assert a['history']==b['history']
    assert len(a['history'])==6 and a['history'][-1]<a['history'][0]
    np.testing.assert_array_equal(t,np.zeros(4))


def test_paired_percentage_points():
    rows=[{'seed':s,'variant':v,'test_accuracy':acc} for s in range(2) for v,acc in [('RY',0.7),('ZZ',0.76)]]
    result=summarize(rows)
    assert result['delta_pp']==pytest.approx(6); assert result['prediction_met']
    with pytest.raises(ValueError): summarize(rows[:-1])


def test_roundtrip(tmp_path):
    p=tmp_path/'metrics.json'; save_json(p,{'a':[1,2],'score':0.8}); assert load_json(p)=={'a':[1,2],'score':0.8}


def test_resource_comparison():
    ry=resources('RY'); zz=resources('ZZ')
    assert ry['two_qubit_gates']==2 and zz['two_qubit_gates']==4
    assert zz['depth']>ry['depth']


def test_cli_artifacts_and_frozen_protocol(tmp_path):
    from run_experiment import run, audit_results
    protocol=json.loads(open('experiment_protocol.json',encoding='utf-8').read())
    original=json.dumps(protocol,sort_keys=True)
    run(tmp_path,protocol,seeds=[0],steps=2,validation_only=True)
    assert json.dumps(protocol,sort_keys=True)==original
    assert (tmp_path/'metrics.csv').exists()
    assert (tmp_path/'histories.json').exists()
    assert (tmp_path/'environment.json').exists()
    audit_results(tmp_path,expected_seeds=[0],expected_steps=2)


def test_invalid_encoding():
    with pytest.raises(ValueError): encoding_circuit([0.2,0.4],'bad')


def test_zz_zero_phi():
    x=np.array([np.pi,0.7]); expected=np.exp(1j*(np.pi*np.array([1,-1,1,-1])+0.7*np.array([1,1,-1,-1])))/2
    np.testing.assert_allclose(Statevector.from_instruction(encoding_circuit(x,'ZZ')).data,expected,atol=1e-14)


def test_last_target_rotation_is_unobservable():
    x=np.array([[0.2,0.7],[1.2,2.1]])
    for variant in ['RY','ZZ']:
        states=encoded_states(x,variant)
        np.testing.assert_allclose(probabilities(states,[0.1,0.2,0.3,0.4]),probabilities(states,[0.1,0.2,0.3,2.4]),atol=1e-14)


def test_ry_can_represent_xor_boundary_analytically():
    x=np.random.default_rng(40).uniform(0,np.pi,(100,2))
    p=probabilities(encoded_states(x,'RY'),[np.pi/2,np.pi/2,-np.pi/2,0])
    np.testing.assert_allclose(1-2*p,np.cos(x[:,0])*np.cos(x[:,1]),atol=1e-14)
    np.testing.assert_array_equal(predict(p),((x[:,0]-np.pi/2)*(x[:,1]-np.pi/2)<0).astype(int))
